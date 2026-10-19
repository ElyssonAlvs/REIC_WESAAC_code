"""Biblioteca de ferramentas determinísticas do Sprint Planning Multi-Agent System."""

from collections import deque
from typing import Any, Union
from langchain_core.tools import tool

from sprint_mas.state import Allocation, DeveloperProfile, Task


@tool
def calculate_team_capacity(
    team_profiles: list[Union[dict, DeveloperProfile]],
    sprint_days: int = 10,
    points_per_day: float = 2.0,
) -> dict[str, Any]:
    """Calcula a capacidade máxima analítica por desenvolvedor e total do time.

    Fórmula: max_pts = round(fte * sprint_days * points_per_day, 1)

    Args:
        team_profiles: Lista de perfis de desenvolvedores (DeveloperProfile ou dicionários).
        sprint_days: Duração da sprint em dias úteis (default: 10, deve ser > 0).
        points_per_day: Taxa nominal de story points por dia de dedicação total (default: 2.0, deve ser > 0).

    Returns:
        dict[str, Any]: Dicionário contendo capacidades individuais e capacidade total do time.

    Raises:
        ValueError: Se sprint_days ou points_per_day forem <= 0 ou se algum FTE for negativo.
        TypeError: Se algum item em team_profiles for de tipo incompatível.
    """
    if sprint_days <= 0:
        raise ValueError(f"Duração da sprint deve ser maior que zero. Recebido: {sprint_days}")
    if points_per_day <= 0:
        raise ValueError(f"Taxa de pontos por dia deve ser maior que zero. Recebido: {points_per_day}")

    capacities: dict[str, float] = {}

    for profile in team_profiles:
        if isinstance(profile, DeveloperProfile):
            dev_id = profile.id
            fte = profile.fte
        elif isinstance(profile, dict):
            dev_id = str(profile.get("id"))
            fte = float(profile.get("fte", 1.0))
        else:
            raise TypeError(f"Tipo de perfil inválido: {type(profile)}. Esperava-se dict ou DeveloperProfile.")

        if fte < 0.0:
            raise ValueError(f"FTE do desenvolvedor '{dev_id}' não pode ser negativo: {fte}")

        max_points = round(fte * sprint_days * points_per_day, 1)
        capacities[dev_id] = max_points

    total_capacity = round(sum(capacities.values()), 1)

    return {
        "capacities": capacities,
        "total_team_capacity": total_capacity,
        "sprint_days": sprint_days,
        "points_per_day": points_per_day,
    }


@tool
def check_allocation_feasibility(
    allocations: list[Union[dict, Allocation]],
    team_capacity: dict[str, Any],
    tasks: list[Union[dict, Task]],
) -> dict[str, Any]:
    """Verifica a viabilidade de alocação de tarefas contra os tetos individuais de FTE.

    Soma os story points atribuídos a cada desenvolvedor e compara com o teto estabelecido.
    Identifica com exatidão sobrecargas, violações do teto de capacidade e IDs desconhecidos (anti-IDOR).

    Args:
        allocations: Lista de alocações (Allocation ou dicionários).
        team_capacity: Dicionário contendo as capacidades máximas (ou chave 'capacities').
        tasks: Lista de tarefas para resolução de story points caso omitidos na alocação.

    Returns:
        dict[str, Any]: Relatório contendo 'is_feasible', 'allocated_by_dev' e 'violations'.
    """
    # Resolução do mapa de capacidades
    if "capacities" in team_capacity and isinstance(team_capacity["capacities"], dict):
        max_capacities = team_capacity["capacities"]
    else:
        max_capacities = team_capacity

    # Resolução do mapa de story points por tarefa
    task_points_map: dict[str, int] = {}
    for task in tasks:
        if isinstance(task, Task):
            task_points_map[task.id] = task.story_points
        elif isinstance(task, dict):
            task_id = str(task.get("id"))
            pts = int(task.get("story_points", 0))
            task_points_map[task_id] = pts

    valid_task_ids = set(task_points_map.keys())
    valid_dev_ids = set(max_capacities.keys())

    allocated_by_dev: dict[str, int] = {dev_id: 0 for dev_id in max_capacities.keys()}
    violations: list[str] = []

    for alloc in allocations:
        if isinstance(alloc, Allocation):
            dev_id = alloc.developer_id
            task_id = alloc.task_id
            pts = alloc.allocated_points or task_points_map.get(task_id, 0)
        elif isinstance(alloc, dict):
            dev_id = str(alloc.get("developer_id"))
            task_id = str(alloc.get("task_id"))
            pts = int(alloc.get("allocated_points") or task_points_map.get(task_id, 0))
        else:
            continue

        # Defesa anti-IDOR: validação de existência de entidades
        if dev_id not in valid_dev_ids:
            violations.append(f"Desenvolvedor '{dev_id}' não encontrado na capacidade da equipe.")
        if task_id not in valid_task_ids:
            violations.append(f"Tarefa '{task_id}' não encontrada no backlog da sprint.")

        if dev_id not in allocated_by_dev:
            allocated_by_dev[dev_id] = 0

        allocated_by_dev[dev_id] += pts

    # Verificação de violações de teto
    for dev_id, allocated_pts in allocated_by_dev.items():
        if dev_id in max_capacities:
            max_cap = max_capacities.get(dev_id, 0.0)
            if allocated_pts > max_cap:
                violations.append(
                    f"Desenvolvedor '{dev_id}' alocado com {allocated_pts} pts, "
                    f"excedendo a capacidade máxima de {max_cap} pts."
                )

    is_feasible = (len(violations) == 0)

    return {
        "is_feasible": is_feasible,
        "allocated_by_dev": allocated_by_dev,
        "violations": violations,
    }


@tool
def get_topological_order(tasks: list[Union[dict, Task]]) -> list[str]:
    """Calcula a ordenação topológica causal de execução do grafo acíclico de dependências.

    Garante que se uma tarefa A depende de B, a tarefa B obrigatoriamente precederá A
    na sequência de IDs retornada.

    Args:
        tasks: Lista de tarefas a serem ordenadas (Task ou dicionários).

    Returns:
        list[str]: Sequência ordenada de IDs de tarefas respeitando as dependências causais.

    Raises:
        ValueError: Caso exista dependência órfã ou ciclo de dependência circular.
    """
    in_degree: dict[str, int] = {}
    dependents: dict[str, list[str]] = {}
    all_ids: set[str] = set()

    # Extração de IDs e dependências
    task_deps_map: dict[str, list[str]] = {}
    for task in tasks:
        if isinstance(task, Task):
            tid = task.id
            deps = list(task.dependencies)
        elif isinstance(task, dict):
            tid = str(task.get("id"))
            deps = list(task.get("dependencies", []))
        else:
            continue

        all_ids.add(tid)
        task_deps_map[tid] = deps
        in_degree[tid] = len(deps)
        dependents[tid] = []

    # Validação prévia de dependências órfãs
    for tid, deps in task_deps_map.items():
        for dep in deps:
            if dep not in all_ids:
                raise ValueError(
                    f"Dependência órfã detectada: tarefa '{tid}' depende de '{dep}', "
                    "que não existe no conjunto de tarefas fornecido."
                )

    # Construção do grafo inverso (predecessor -> dependentes)
    for tid, deps in task_deps_map.items():
        for dep in deps:
            if dep not in dependents:
                dependents[dep] = []
            dependents[dep].append(tid)

    # Fila de tarefas sem dependências pendentes (in_degree == 0)
    queue = deque([tid for tid in all_ids if in_degree[tid] == 0])
    ordered_ids: list[str] = []

    while queue:
        current = queue.popleft()
        ordered_ids.append(current)

        for dep_task in dependents.get(current, []):
            in_degree[dep_task] -= 1
            if in_degree[dep_task] == 0:
                queue.append(dep_task)

    if len(ordered_ids) < len(all_ids):
        unresolved = set(all_ids) - set(ordered_ids)
        raise ValueError(
            f"Ciclo de dependência circular detectado. "
            f"Não foi possível ordenar as tarefas: {unresolved}."
        )

    return ordered_ids


@tool
def match_skills(task_skill: str, dev_skills: list[str]) -> bool:
    """Verifica se as competências do desenvolvedor satisfazem o requisito da tarefa.

    Regra de equivalência:
    - Correspondência direta exata (case-insensitive).
    - Habilidade 'fullstack' satisfaz requisitos de 'backend', 'frontend' ou 'fullstack'.

    Args:
        task_skill: Habilidade exigida pela tarefa (ex: 'backend', 'frontend', 'ui').
        dev_skills: Lista de competências dominadas pelo desenvolvedor.

    Returns:
        bool: True se o desenvolvedor estiver capacitado, False caso contrário.
    """
    clean_task_skill = task_skill.strip().lower()
    clean_dev_skills = [s.strip().lower() for s in dev_skills]

    # Match direto
    if clean_task_skill in clean_dev_skills:
        return True

    # Equivalência de perfil Fullstack
    if "fullstack" in clean_dev_skills and clean_task_skill in ("backend", "frontend", "fullstack"):
        return True

    return False
