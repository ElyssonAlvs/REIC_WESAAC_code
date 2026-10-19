"""Módulo responsável pelo carregamento e validação de cenários de teste e grafos de dependência."""

import json
from pathlib import Path

from sprint_mas.state import DeveloperProfile, Task


def get_data_dir() -> Path:
    """Localiza dinamicamente o diretório 'data' do projeto.

    Returns:
        Path: Caminho absoluto para a pasta 'data'.
    """
    # Localização a partir deste arquivo: REIC-WESAAC/sprint_mas/data_loader.py -> REIC-WESAAC/data
    data_dir = Path(__file__).resolve().parent.parent / "data"
    if data_dir.is_dir():
        return data_dir

    # Fallback caso executado a partir do CWD
    cwd_data = Path.cwd() / "data"
    if cwd_data.is_dir():
        return cwd_data

    return data_dir


def list_available_scenarios() -> list[str]:
    """Retorna a lista ordenada dos nomes dos cenários disponíveis em data/processed.

    Returns:
        list[str]: Lista ordenada com os nomes dos cenários (sem a extensão .json).
    """
    processed_dir = get_data_dir() / "processed"
    if not processed_dir.is_dir():
        return []

    scenarios = [
        file.stem
        for file in processed_dir.glob("*.json")
        if file.is_file()
    ]
    return sorted(scenarios)


def validate_dependencies_dag(tasks: list[Task]) -> None:
    """Valida a integridade do Grafo Direcionado Acíclico (DAG) de dependências.

    Verificações realizadas:
    1. Unicidade de IDs das tarefas.
    2. Auto-dependência (tarefa dependendo de si mesma).
    3. Dependências órfãs (referência a ID inexistente na lista de tarefas).
    4. Ciclos de dependência em qualquer extensão (ex: A -> B -> A ou A -> B -> C -> A).

    Args:
        tasks: Lista de tarefas a serem validadas.

    Raises:
        ValueError: Caso seja detectada auto-dependência, dependência órfã,
            duplicidade de IDs ou ciclos no grafo.
    """
    task_map: dict[str, Task] = {}
    for task in tasks:
        if task.id in task_map:
            raise ValueError(
                f"ID de tarefa duplicado detectado no backlog: '{task.id}'."
            )
        task_map[task.id] = task

    all_ids = set(task_map.keys())

    # Validação de auto-dependência e referências órfãs
    for task in tasks:
        for dep_id in task.dependencies:
            if dep_id == task.id:
                raise ValueError(
                    f"Auto-dependência detectada: a tarefa '{task.id}' depende de si mesma."
                )
            if dep_id not in all_ids:
                raise ValueError(
                    f"Dependência órfã detectada: a tarefa '{task.id}' depende de '{dep_id}', "
                    "que não existe no backlog."
                )

    # Detecção de ciclos via DFS com marcação de 3 cores:
    # 0 = WHITE (não visitado), 1 = GRAY (em processamento no caminho atual), 2 = BLACK (processado)
    color: dict[str, int] = {task_id: 0 for task_id in all_ids}
    path: list[str] = []

    def dfs(current_id: str) -> None:
        color[current_id] = 1  # GRAY
        path.append(current_id)

        for dep_id in task_map[current_id].dependencies:
            if color[dep_id] == 1:
                # Encontrou nó GRAY: ciclo detectado
                cycle_start_index = path.index(dep_id)
                cycle_nodes = path[cycle_start_index:] + [dep_id]
                cycle_repr = " -> ".join(cycle_nodes)
                raise ValueError(
                    f"Ciclo de dependência circular detectado no backlog: {cycle_repr}."
                )
            if color[dep_id] == 0:
                dfs(dep_id)

        path.pop()
        color[current_id] = 2  # BLACK

    for task_id in all_ids:
        if color[task_id] == 0:
            dfs(task_id)


def load_scenario(scenario_name: str) -> tuple[list[Task], list[DeveloperProfile]]:
    """Carrega um cenário de teste a partir de data/processed/ e valida seus dados.

    Aceita nomenclaturas flexíveis: 'scenario_a', 'scenario_b', 'scenario_c' ou 'a', 'b', 'c'.

    Args:
        scenario_name: Nome do cenário desejado.

    Returns:
        tuple[list[Task], list[DeveloperProfile]]: Tupla contendo a lista de tarefas
            validadas e a equipe de desenvolvedores.

    Raises:
        FileNotFoundError: Se o arquivo do cenário não existir em data/processed/.
        ValueError: Se houver IDs duplicados ou inconsistências no grafo de dependências.
    """
    clean_name = scenario_name.strip().lower()
    if clean_name.endswith(".json"):
        clean_name = clean_name[:-5]
    if not clean_name.startswith("scenario_"):
        clean_name = f"scenario_{clean_name}"

    file_path = get_data_dir() / "processed" / f"{clean_name}.json"
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Cenário não encontrado: '{scenario_name}'. "
            f"O arquivo correspondente não existe em '{file_path}'."
        )

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_tasks = data.get("tasks", [])
    raw_team = data.get("team", [])

    tasks = [Task(**t) for t in raw_tasks]
    team = [DeveloperProfile(**d) for d in raw_team]

    # Validação de unicidade de IDs de tarefas
    seen_task_ids: set[str] = set()
    for task in tasks:
        if task.id in seen_task_ids:
            raise ValueError(
                f"ID de tarefa duplicado detectado no cenário '{scenario_name}': '{task.id}'."
            )
        seen_task_ids.add(task.id)

    # Validação de unicidade de IDs de desenvolvedores
    seen_dev_ids: set[str] = set()
    for dev in team:
        if dev.id in seen_dev_ids:
            raise ValueError(
                f"ID de desenvolvedor duplicado detectado no cenário '{scenario_name}': '{dev.id}'."
            )
        seen_dev_ids.add(dev.id)

    # Validação do grafo de dependências (órfãos, auto-dependência e ciclos)
    validate_dependencies_dag(tasks)

    return tasks, team
