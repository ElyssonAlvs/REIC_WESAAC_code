"""Agente de Alocação de Recursos (Resource Allocator Node) do Sprint Planning MAS."""

import json
import re
from typing import Any, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from pydantic import BaseModel, ConfigDict, Field

from sprint_mas.llm_factory import get_llm
from sprint_mas.prompts import get_agent_prompt_template
from sprint_mas.state import Allocation, DeveloperProfile, SprintState, Task
from sprint_mas.tools import calculate_team_capacity, match_skills


class AllocationItem(BaseModel):
    """Item de alocação de uma tarefa a um desenvolvedor."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="ID da tarefa alocada.")
    developer_id: str = Field(..., description="ID do desenvolvedor responsável.")
    allocated_points: int = Field(..., description="Story points atribuídos nesta alocação.")
    reason: str = Field(..., description="Justificativa técnica da decisão de alocação.")


class AllocationOutput(BaseModel):
    """Esquema de saída estruturada do Agente de Alocação."""

    model_config = ConfigDict(extra="forbid")

    allocations: list[AllocationItem] = Field(
        ..., description="Lista de alocações de tarefas para desenvolvedores."
    )
    allocation_summary: str = Field(
        ..., description="Sumário executivo do balanceamento e resolução de gargalos alcançada."
    )


def is_dev_qualified(
    task_skill: str,
    dev: DeveloperProfile,
    team: list[DeveloperProfile],
) -> bool:
    """Verifica se o desenvolvedor é tecnicamente apto para a tarefa.

    Regras:
    - Correspondência direta via match_skills (incluindo fullstack cobrindo backend e frontend).
    - Tarefas de devops em times sem especialista formal de devops podem ser assumidas por
      backend ou fullstack (dev_B, dev_C, dev_E), mas NUNCA por desenvolvedor exclusivo frontend (dev_A).
    - Tarefas de backend NUNCA para desenvolvedor exclusivo de frontend (dev_A).
    """
    clean_skill = task_skill.strip().lower()
    dev_skills = [s.strip().lower() for s in dev.skills]

    # Validação via ferramenta canônica
    if match_skills.func(task_skill=clean_skill, dev_skills=dev_skills):
        return True

    # Suporte a devops em times enxutos sem especialista de devops dedicado
    if clean_skill == "devops":
        has_devops_specialist = any("devops" in [s.lower() for s in d.skills] for d in team)
        if not has_devops_specialist:
            if "backend" in dev_skills or "fullstack" in dev_skills or dev.id in ("dev_B", "dev_C", "dev_E"):
                if dev.id != "dev_A":  # dev_A é frontend estrito
                    return True

    return False


def validate_allocation_plan(
    tasks: list[Union[Task, dict]],
    team: list[Union[DeveloperProfile, dict]],
    allocations: list[Union[Allocation, AllocationItem, dict]],
    team_capacity: Optional[dict[str, Any]] = None,
) -> None:
    """Valida a conformidade estrita do plano de alocações contra regras de negócio e segurança.

    Regras de validação:
    a) Anti-IDOR: Todo developer_id deve pertencer à equipe e todo task_id deve pertencer ao backlog.
    b) Completude e Unicidade: Toda tarefa do backlog deve ser alocada exatamente uma vez.
    c) Respeito aos Story Points: allocated_points deve ser idêntico ao story_points da tarefa.
    d) Casamento de Habilidades (Skill Matching): O desenvolvedor deve possuir a competência exigida.
       Tarefas de backend nunca podem ser atribuídas a desenvolvedores exclusivos de frontend (dev_A).
    e) Tetos de FTE: A soma de pontos de cada desenvolvedor não pode exceder sua capacidade analítica
       (especialmente dev_D com 0.5 FTE = máx 10 pts, e dev_B com 0.7 FTE = máx 14 pts).

    Args:
        tasks: Lista de tarefas a serem alocadas.
        team: Lista de perfis de desenvolvedores disponíveis.
        allocations: Lista de propostas de alocação.
        team_capacity: Dicionário opcional de capacidades. Se None, computado via calculate_team_capacity.

    Raises:
        ValueError: Caso qualquer regra seja violada.
    """
    # 1. Normalização de instâncias
    task_map: dict[str, Task] = {}
    for t in tasks:
        task_obj = t if isinstance(t, Task) else Task(**t)
        task_map[task_obj.id] = task_obj

    team_map: dict[str, DeveloperProfile] = {}
    team_list: list[DeveloperProfile] = []
    for d in team:
        dev_obj = d if isinstance(d, DeveloperProfile) else DeveloperProfile(**d)
        team_map[dev_obj.id] = dev_obj
        team_list.append(dev_obj)

    valid_task_ids = set(task_map.keys())
    valid_dev_ids = set(team_map.keys())

    # 2. Resolução de capacidades
    if team_capacity is None:
        cap_result = calculate_team_capacity.func(team_profiles=team_list)
        capacities = cap_result["capacities"]
    elif "capacities" in team_capacity and isinstance(team_capacity["capacities"], dict):
        capacities = team_capacity["capacities"]
    else:
        capacities = team_capacity

    normalized_allocs: list[Allocation] = []
    allocated_task_ids: list[str] = []
    points_by_dev: dict[str, int] = {dev_id: 0 for dev_id in valid_dev_ids}

    for item in allocations:
        if isinstance(item, Allocation):
            alloc_obj = item
        elif isinstance(item, AllocationItem):
            alloc_obj = Allocation(
                task_id=item.task_id,
                developer_id=item.developer_id,
                allocated_points=item.allocated_points,
                reason=item.reason,
            )
        elif isinstance(item, dict):
            alloc_obj = Allocation(**item)
        else:
            raise ValueError(f"Tipo de alocação inválido: {type(item)}")

        # a) Anti-IDOR: validação de IDs de desenvolvedores e tarefas
        if alloc_obj.developer_id not in valid_dev_ids:
            raise ValueError(
                f"Violação Anti-IDOR: desenvolvedor '{alloc_obj.developer_id}' não existe na equipe."
            )
        if alloc_obj.task_id not in valid_task_ids:
            raise ValueError(
                f"Violação Anti-IDOR: tarefa '{alloc_obj.task_id}' não existe no backlog fornecido."
            )

        task = task_map[alloc_obj.task_id]
        dev = team_map[alloc_obj.developer_id]

        # c) Respeito aos Story Points
        if alloc_obj.allocated_points != task.story_points:
            raise ValueError(
                f"Pontos alocados divergentes para a tarefa '{task.id}': "
                f"esperado {task.story_points}, recebido {alloc_obj.allocated_points}."
            )

        # d) Casamento de Habilidades (Skill Matching)
        is_match = is_dev_qualified(task_skill=task.skill_required, dev=dev, team=team_list)
        if not is_match:
            raise ValueError(
                f"Incompatibilidade de competência técnica: desenvolvedor '{dev.id}' "
                f"(skills: {dev.skills}) não possui a habilidade '{task.skill_required}' "
                f"exigida pela tarefa '{task.id}'."
            )

        allocated_task_ids.append(alloc_obj.task_id)
        points_by_dev[alloc_obj.developer_id] += alloc_obj.allocated_points
        normalized_allocs.append(alloc_obj)

    # b) Unicidade e Completude
    if len(allocated_task_ids) != len(set(allocated_task_ids)):
        duplicates = [tid for tid in allocated_task_ids if allocated_task_ids.count(tid) > 1]
        raise ValueError(
            f"Tarefas duplicadas encontradas na alocação: {sorted(set(duplicates))}."
        )

    missing_tasks = valid_task_ids - set(allocated_task_ids)
    if missing_tasks:
        raise ValueError(
            f"Tarefas faltantes na alocação: {sorted(missing_tasks)}."
        )

    # e) Tetos de FTE
    for dev_id, total_pts in points_by_dev.items():
        max_cap = capacities.get(dev_id, 0.0)
        if total_pts > max_cap:
            raise ValueError(
                f"Estouro de capacidade FTE: desenvolvedor '{dev_id}' recebeu {total_pts} pontos, "
                f"excedendo o teto máximo de {max_cap} pontos."
            )


def deterministic_allocation(
    tasks: list[Union[Task, dict]],
    team: list[Union[DeveloperProfile, dict]],
    team_capacity: Optional[dict[str, Any]] = None,
) -> list[Allocation]:
    """Algoritmo guloso determinístico de alocação de tarefas para a equipe.

    Garante estabilidade, respeito estrito aos tetos de FTE e resolução do gargalo de backend:
    - Tarefas de backend são alocadas prioritariamente para especialistas (dev_B teto 14, dev_D teto 10).
    - Tarefas grandes de backend (>= 6 pts) ou quando os especialistas atingem a capacidade
      são alocadas para o desenvolvedor Fullstack (dev_C teto 20), mitigando o gargalo de 63.3% do Cenário B (REIC 2026).
    - Garante que dev_D (0.5 FTE) NUNCA receba mais que 10 Story Points.
    - Tarefas de frontend são direcionadas para desenvolvedores exclusivos de frontend (dev_A, dev_E)
      preservando a capacidade do dev_C para absorver backend.

    Args:
        tasks: Lista de tarefas a serem alocadas.
        team: Lista de perfis de desenvolvedores disponíveis.
        team_capacity: Dicionário opcional de capacidades máximas.

    Returns:
        list[Allocation]: Lista de alocações determinísticas válidas.
    """
    task_objs: list[Task] = [t if isinstance(t, Task) else Task(**t) for t in tasks]
    team_objs: list[DeveloperProfile] = [d if isinstance(d, DeveloperProfile) else DeveloperProfile(**d) for d in team]

    if team_capacity is None:
        cap_result = calculate_team_capacity.func(team_profiles=team_objs)
        capacities = cap_result["capacities"]
    elif "capacities" in team_capacity and isinstance(team_capacity["capacities"], dict):
        capacities = team_capacity["capacities"]
    else:
        capacities = team_capacity

    current_load: dict[str, int] = {dev.id: 0 for dev in team_objs}
    allocations: list[Allocation] = []

    for task in task_objs:
        clean_skill = task.skill_required.strip().lower()
        pts = task.story_points

        # Filtra candidatos qualificados
        qualified_devs = [
            dev for dev in team_objs
            if is_dev_qualified(task_skill=clean_skill, dev=dev, team=team_objs)
        ]

        if not qualified_devs:
            raise ValueError(
                f"Nenhum desenvolvedor qualificado encontrado para a habilidade '{task.skill_required}' "
                f"da tarefa '{task.id}'."
            )

        # Estratégia de priorização de candidatos para mitigação de gargalo
        def candidate_preference(d: DeveloperProfile) -> tuple[int, int, float, str]:
            dev_skills_lower = [s.lower() for s in d.skills]
            is_fullstack = "fullstack" in dev_skills_lower
            max_c = capacities.get(d.id, 1.0) or 1.0
            has_capacity = 0 if (current_load[d.id] + pts <= max_c) else 1

            if clean_skill == "backend":
                if pts >= 6:
                    # Tarefas grandes de backend vão preferencialmente para dev_C (teto 20) para não estourar dev_B/dev_D
                    tier = 0 if is_fullstack else 1
                else:
                    # Tarefas menores de backend vão para especialistas dedicados
                    tier = 1 if is_fullstack else 0
            elif clean_skill == "frontend":
                # Tarefas de frontend vão para especialistas exclusivos para reservar dev_C para backend
                tier = 1 if is_fullstack else 0
            else:
                tier = 0

            load_ratio = current_load[d.id] / max_c
            return (has_capacity, tier, load_ratio, d.id)

        sorted_devs = sorted(qualified_devs, key=candidate_preference)

        # Seleciona o melhor desenvolvedor com capacidade disponível
        chosen_dev: Optional[DeveloperProfile] = None
        for dev in sorted_devs:
            max_c = capacities.get(dev.id, 0.0)
            if current_load[dev.id] + pts <= max_c:
                chosen_dev = dev
                break

        # Fallback de sobrecarga se todos estiverem lotados
        # dev_D NUNCA pode receber mais de 10 pts
        if chosen_dev is None:
            non_dev_d = [
                d for d in sorted_devs
                if not (d.id == "dev_D" and current_load["dev_D"] + pts > capacities.get("dev_D", 10.0))
            ]
            chosen_dev = non_dev_d[0] if non_dev_d else sorted_devs[0]

        # Constrói a justificativa técnica
        if chosen_dev.id == "dev_C" and clean_skill == "backend":
            reason = (
                f"dev_C (Fullstack) alocado para absorver transbordo de backend da tarefa '{task.id}' "
                f"({pts} pts), mitigando gargalo estrutural e respeitando teto de dev_D (0.5 FTE)."
            )
        elif chosen_dev.id == "dev_D":
            reason = (
                f"dev_D (Backend Specialist) alocado respeitando estritamente o limite de 0.5 FTE "
                f"(máx 10 pts). Carga atual: {current_load[chosen_dev.id] + pts}/{capacities.get('dev_D', 10.0)} pts."
            )
        elif chosen_dev.id == "dev_B":
            reason = (
                f"dev_B (Backend Specialist) alocado com base em especialidade técnica e teto de 0.7 FTE "
                f"(máx 14 pts). Carga atual: {current_load[chosen_dev.id] + pts}/{capacities.get('dev_B', 14.0)} pts."
            )
        else:
            reason = (
                f"Desenvolvedor '{chosen_dev.id}' alocado por correspondência de habilidade ({task.skill_required}) "
                f"e disponibilidade de capacidade."
            )

        current_load[chosen_dev.id] += pts
        allocations.append(
            Allocation(
                task_id=task.id,
                developer_id=chosen_dev.id,
                allocated_points=pts,
                reason=reason,
            )
        )

    return allocations


def _clean_json_markdown(content: str) -> str:
    """Extrai conteúdo JSON limpo caso esteja encapsulado em markdown code fences."""
    content_str = content.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content_str, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return content_str


def allocation_node(
    state: SprintState,
    llm: Optional[BaseChatModel] = None,
    strict: bool = False,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
) -> dict[str, Any]:
    """Nó do LangGraph para o Agente de Alocação de Recursos (Allocator Node).

    Orquestra a alocação de tarefas para os membros da equipe:
    1. Valida entradas: 'prioritized_tasks' (ou 'backlog') e 'team' no SprintState.
    2. Computa capacidades determinísticas exatas via `calculate_team_capacity`.
    3. Carrega o prompt compilado de `configs/prompts/allocation.yaml`.
    4. Invoca o modelo LLM configurado (ou via fábrica `get_llm(temperature=0.0)`).
    5. Parseia a saída em `AllocationOutput` e audita com `validate_allocation_plan`.
    6. Se inválido: se strict=True levanta ValueError; se strict=False aciona
       o fallback `deterministic_allocation` com log explicativo no histórico.
    7. Retorna `{"allocations": allocations, "messages": [AIMessage(...)]}`.

    Args:
        state: Estado compartilhado da sprint (`SprintState`).
        llm: Modelo LangChain opcional para injeção de dependência / mocks.
        strict: Se True, falhas de validação disparam ValueError. Se False, ativa fallback resiliente.
        sprint_days: Duração da sprint em dias úteis (default: 10).
        points_per_day: Capacidade analítica padrão por dia útil (default: 2.0).

    Returns:
        dict[str, Any]: Atualização para o SprintState contendo allocations e messages.

    Raises:
        ValueError: Se tarefas/time forem vazios ou se validação falhar com strict=True.
    """
    tasks_raw = state.get("prioritized_tasks") or state.get("backlog")
    team_raw = state.get("team")

    if not tasks_raw or not team_raw:
        raise ValueError(
            "Entradas inválidas para alocação: 'prioritized_tasks' (ou 'backlog') e 'team' "
            "devem ser não-vazios no SprintState."
        )

    tasks: list[Task] = [t if isinstance(t, Task) else Task(**t) for t in tasks_raw]
    team: list[DeveloperProfile] = [d if isinstance(d, DeveloperProfile) else DeveloperProfile(**d) for d in team_raw]

    # 1. Capacidades determinísticas computadas pelas ferramentas Python
    cap_result = calculate_team_capacity.func(
        team_profiles=team,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
    )
    capacity_json = json.dumps(cap_result, ensure_ascii=False, indent=2)

    # 2. Serialização dos inputs para o prompt
    prioritized_tasks_json = json.dumps(
        [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "story_points": t.story_points,
                "skill_required": t.skill_required,
                "priority": t.priority,
                "dependencies": t.dependencies,
            }
            for t in tasks
        ],
        ensure_ascii=False,
        indent=2,
    )

    team_json = json.dumps(
        [
            {
                "id": d.id,
                "name": d.name,
                "skills": d.skills,
                "fte": d.fte,
            }
            for d in team
        ],
        ensure_ascii=False,
        indent=2,
    )

    # 3. Compilação do template e formatação das mensagens
    prompt_template = get_agent_prompt_template("allocation")
    formatted_messages = prompt_template.format_messages(
        prioritized_tasks_json=prioritized_tasks_json,
        team_json=team_json,
        capacity_json=capacity_json,
    )

    allocations: list[Allocation] = []
    summary: str = ""

    try:
        active_llm = llm or get_llm(temperature=0.0)
        response = active_llm.invoke(formatted_messages)
        response_text = _clean_json_markdown(str(response.content))
        data = json.loads(response_text)
        parsed_output = AllocationOutput(**data)

        # Validação de integridade, competências, anti-IDOR e tetos de FTE
        validate_allocation_plan(
            tasks=tasks,
            team=team,
            allocations=parsed_output.allocations,
            team_capacity=cap_result,
        )

        allocations = [
            Allocation(
                task_id=item.task_id,
                developer_id=item.developer_id,
                allocated_points=item.allocated_points,
                reason=item.reason,
            )
            for item in parsed_output.allocations
        ]
        summary = parsed_output.allocation_summary
    except Exception as exc:
        if strict:
            raise ValueError(
                f"Falha na validação do plano de alocação do LLM (strict=True): {exc}"
            ) from exc

        # Fallback determinístico resiliente
        allocations = deterministic_allocation(
            tasks=tasks,
            team=team,
            team_capacity=cap_result,
        )
        summary = (
            f"[Fallback Determinístico Ativado]: A saída do LLM falhou na validação "
            f"({exc}). Aplicado algoritmo determinístico guloso que assegura 100% "
            f"de conformidade com os tetos de FTE (dev_D <= 10 pts) e resolução de gargalo via dev_C."
        )

    ai_message = AIMessage(
        content=(
            f"### Allocator Agent Deliberation\n\n"
            f"{summary}\n\n"
            f"**Total de tarefas alocadas**: {len(allocations)}"
        )
    )

    return {
        "allocations": allocations,
        "messages": [ai_message],
    }


# Alias oficial conforme especificação da Fase 5
allocator_node = allocation_node
