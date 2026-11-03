"""Orquestração Cíclica do Grafo LangGraph e Ciclo Percepção-Ação (graph.py)."""

from typing import Any, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from sprint_mas.agents.allocator import allocation_node, deterministic_allocation
from sprint_mas.agents.prioritizer import (
    deterministic_topological_sort,
    prioritizer_node,
)
from sprint_mas.agents.supervisor import supervisor_node
from sprint_mas.agents.validator import validation_node
from sprint_mas.llm_factory import get_llm
from sprint_mas.state import DeveloperProfile, SprintState, Task
from sprint_mas.telemetry import build_langsmith_run_config
from sprint_mas.tools import calculate_team_capacity


class OfflineFallbackChatModel(BaseChatModel):
    """Offline chat model that raises RuntimeError upon invocation to trigger deterministic fallbacks."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise RuntimeError("Offline mode: triggering agent deterministic fallbacks.")

    @property
    def _llm_type(self) -> str:
        return "offline_fallback"


def _resolve_llm(llm: Optional[BaseChatModel] = None) -> Optional[BaseChatModel]:
    """Resolves the LLM to use: user-provided model, configured factory model, or offline fallback."""
    if llm is not None:
        return llm
    try:
        return get_llm(temperature=0.0)
    except Exception:
        return OfflineFallbackChatModel()


def select_feasible_sprint_tasks(
    tasks: list[Union[Task, dict]],
    team: list[Union[DeveloperProfile, dict]],
    team_capacity: Optional[dict[str, Any]] = None,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
) -> list[Task]:
    """Algoritmo determinístico de seleção de escopo por capacidade e causalidade DAG.

    Seleciona o maior subconjunto viável de tarefas para a sprint:
    1. Analisa tarefas na ordem topológica/priorizada (respeitando desempate de valor de negócio).
    2. Garante que para selecionar uma tarefa, todas as suas dependências DAG já estejam selecionadas.
    3. Simula alocação gulosa determinística garantindo que nenhum desenvolvedor estoure seu teto FTE
       (especialmente dev_D <= 10.0, dev_B <= 14.0, dev_C <= 20.0, e equipe total <= 84 no Cenário B).

    Args:
        tasks: Lista de tarefas candidatas.
        team: Lista de perfis de desenvolvedores disponíveis.
        team_capacity: Dicionário opcional pré-computado de capacidades máximas.
        sprint_days: Duração da sprint em dias úteis (default: 10, deve ser > 0).
        points_per_day: Taxa nominal de story points por dia de dedicação integral (default: 2.0, > 0).

    Returns:
        list[Task]: Subconjunto ordenado de tarefas viáveis para a sprint.

    Raises:
        ValueError: Se sprint_days <= 0, points_per_day <= 0, ou tarefas/time estiverem vazios.
    """
    if sprint_days <= 0:
        raise ValueError(f"sprint_days must be greater than 0, got {sprint_days}.")
    if points_per_day <= 0:
        raise ValueError(f"points_per_day must be greater than 0, got {points_per_day}.")
    if not tasks:
        raise ValueError("Tasks must be non-empty for scope selection.")
    if not team:
        raise ValueError("Team must be non-empty for scope selection.")

    task_objs = [t if isinstance(t, Task) else Task(**t) for t in tasks]
    team_objs = [d if isinstance(d, DeveloperProfile) else DeveloperProfile(**d) for d in team]

    if team_capacity is None:
        cap_res = calculate_team_capacity.func(
            team_profiles=team_objs,
            sprint_days=sprint_days,
            points_per_day=points_per_day,
        )
        capacities = cap_res["capacities"]
        total_team_capacity = cap_res["total_team_capacity"]
    elif "capacities" in team_capacity and isinstance(team_capacity["capacities"], dict):
        capacities = team_capacity["capacities"]
        total_team_capacity = team_capacity.get("total_team_capacity", sum(capacities.values()))
    else:
        capacities = team_capacity
        total_team_capacity = sum(capacities.values())

    # Verifica se as tarefas já estão em ordem causal topológica
    def _is_topologically_ordered(tasks_list: list[Task]) -> bool:
        seen = set()
        for t in tasks_list:
            for dep in t.dependencies:
                if dep not in seen:
                    return False
            seen.add(t.id)
        return True

    if _is_topologically_ordered(task_objs):
        ordered_tasks = task_objs
    else:
        ordered_ids = deterministic_topological_sort(task_objs)
        task_map = {t.id: t for t in task_objs}
        ordered_tasks = [task_map[tid] for tid in ordered_ids]

    selected_tasks: list[Task] = []
    selected_ids: set[str] = set()

    for task in ordered_tasks:
        # Causalidade DAG: todas as dependências da tarefa devem estar no subconjunto selecionado
        if not all(dep_id in selected_ids for dep_id in task.dependencies):
            continue

        candidate_tasks = selected_tasks + [task]
        candidate_total_pts = sum(t.story_points for t in candidate_tasks)
        if candidate_total_pts > total_team_capacity:
            continue

        # Simulação determinística de alocação
        try:
            candidate_allocations = deterministic_allocation(
                tasks=candidate_tasks,
                team=team_objs,
                team_capacity=capacities,
            )
        except Exception:
            continue

        # Verificação rigorosa dos tetos analíticos individuais de FTE
        load_by_dev = {dev.id: 0 for dev in team_objs}
        for alloc in candidate_allocations:
            load_by_dev[alloc.developer_id] += alloc.allocated_points

        fits_ceilings = all(
            load_by_dev[dev_id] <= capacities.get(dev_id, 0.0)
            for dev_id in load_by_dev
        )

        if fits_ceilings:
            selected_tasks.append(task)
            selected_ids.add(task.id)

    return selected_tasks


def corrective_replan_node(
    state: SprintState,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
    enable_scope_trimming: bool = True,
) -> dict[str, Any]:
    """Nó corretivo de replanejamento: cura DAG, auto-ajuste de escopo e redefinição de alocações.

    Quando acionado após rejeição do validator_node:
    1. Aplica select_feasible_sprint_tasks para cortar sobrecarga mantendo causalidade DAG.
    2. Redefine 'allocations' para [] forçando o allocation_node a recalcular com escopo viável.
    3. Emite AIMessage deliberativa de replanejamento no histórico compartilhado.

    Args:
        state: Shared SprintState.
        sprint_days: Duração da sprint em dias úteis (default: 10, > 0).
        points_per_day: Taxa de story points por dia (default: 2.0, > 0).
        enable_scope_trimming: Se True, realiza corte por capacidade. Se False, preserva tarefas.

    Returns:
        dict[str, Any]: Atualização para 'prioritized_tasks', 'allocations' e 'messages'.

    Raises:
        ValueError: Se tarefas ou time forem inválidos.
    """
    tasks_raw = state.get("prioritized_tasks") or state.get("backlog")
    team_raw = state.get("team")

    if not tasks_raw or not team_raw:
        raise ValueError("Invalid inputs for replan: tasks and team must be non-empty.")

    tasks = [t if isinstance(t, Task) else Task(**t) for t in tasks_raw]
    team = [d if isinstance(d, DeveloperProfile) else DeveloperProfile(**d) for d in team_raw]

    if enable_scope_trimming:
        feasible_tasks = select_feasible_sprint_tasks(
            tasks=tasks,
            team=team,
            sprint_days=sprint_days,
            points_per_day=points_per_day,
        )
    else:
        feasible_tasks = list(tasks)

    original_count = len(tasks)
    selected_count = len(feasible_tasks)
    total_pts = sum(t.story_points for t in feasible_tasks)

    ai_message = AIMessage(
        content=(
            f"### Replan Agent Deliberation (Corrective Scope Trimming)\n\n"
            f"**Original tasks**: {original_count}\n"
            f"**Feasible tasks selected**: {selected_count}\n"
            f"**Total points**: {total_pts}\n"
            f"**Scope trimming enabled**: {enable_scope_trimming}\n\n"
            f"Resetting allocations for corrective allocation pass."
        )
    )

    return {
        "prioritized_tasks": feasible_tasks,
        "allocations": [],
        "messages": [ai_message],
    }


def route_after_validation(state: SprintState, max_retries: int = 2) -> str:
    """Aresta condicional pós-validação com Circuit Breaker stateless anti-loop infinito.

    Regras de Roteamento:
    - Se 'validation_errors' estiver vazio: retorna 'supervisor'.
    - Se houver violações:
      - Conta o número de deliberações do Validator Agent na janela corrente de execução.
      - Se tentativas <= max_retries: retorna 'replan' (auto-correção).
      - Se tentativas > max_retries: desvia obrigatoriamente para 'supervisor' (rejeição formal segura).

    Args:
        state: Shared SprintState contendo validation_errors e messages.
        max_retries: Número máximo de tentativas de replanejamento (0 <= max_retries <= 10).

    Returns:
        str: Próximo nó de execução ('replan' ou 'supervisor').

    Raises:
        ValueError: Se max_retries estiver fora do intervalo permitido [0, 10].
    """
    if max_retries < 0 or max_retries > 10:
        raise ValueError(f"max_retries must be between 0 and 10, got {max_retries}.")

    if not state.get("validation_errors"):
        return "supervisor"

    messages = state.get("messages", []) or []
    last_prioritizer_idx = 0
    for i, msg in enumerate(messages):
        content = str(getattr(msg, "content", ""))
        if "### Prioritizer Agent Deliberation" in content:
            last_prioritizer_idx = i

    validator_attempts = sum(
        1 for msg in messages[last_prioritizer_idx:]
        if "### Validator Agent Deliberation" in str(getattr(msg, "content", ""))
    )

    if validator_attempts == 0 and state.get("validation_errors"):
        validator_attempts = 1

    if validator_attempts <= max_retries:
        return "replan"

    return "supervisor"


def create_memory_checkpointer() -> MemorySaver:
    """Instancia MemorySaver para isolamento de sessões thread_id."""
    return MemorySaver()


def build_sprint_graph(
    checkpointer: Optional[Any] = None,
    max_retries: int = 2,
    llm: Optional[BaseChatModel] = None,
    strict: bool = False,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
    enable_scope_trimming: bool = True,
    sprint_goal: str = "Deliver prioritized and feasible sprint backlog.",
) -> CompiledStateGraph:
    """Compila a arquitetura completa do Grafo de Estado Cíclico do LangGraph.

    Topologia:
    START -> prioritizer -> allocator -> validator -> (route_after_validation) -> replan -> allocator
    validator -> (route_after_validation) -> supervisor -> END

    Args:
        checkpointer: Checkpointer opcional para persistência e isolamento (ex: MemorySaver).
        max_retries: Teto do circuit breaker de retentativas (default: 2, 0 <= max_retries <= 10).
        llm: Modelo LangChain opcional para injeção de dependências / mocks.
        strict: Se True, falhas no supervisor disparam ValueError.
        sprint_days: Duração da sprint em dias úteis (default: 10, > 0).
        points_per_day: Story points por dia (default: 2.0, > 0).
        enable_scope_trimming: Habilita corte de escopo determinístico no nó corretivo.
        sprint_goal: Objetivo executivo da sprint.

    Returns:
        CompiledStateGraph: Grafo compilado e pronto para execução via invoke().

    Raises:
        ValueError: Se max_retries, sprint_days ou points_per_day forem inválidos.
    """
    if max_retries < 0 or max_retries > 10:
        raise ValueError(f"max_retries must be between 0 and 10, got {max_retries}.")
    if sprint_days <= 0:
        raise ValueError(f"sprint_days must be greater than 0, got {sprint_days}.")
    if points_per_day <= 0:
        raise ValueError(f"points_per_day must be greater than 0, got {points_per_day}.")

    resolved_llm = _resolve_llm(llm)

    def _prioritizer_step(state: SprintState) -> dict[str, Any]:
        return prioritizer_node(state, llm=resolved_llm, strict=strict)

    def _allocator_step(state: SprintState) -> dict[str, Any]:
        return allocation_node(state, llm=resolved_llm, strict=strict)

    def _validator_step(state: SprintState) -> dict[str, Any]:
        return validation_node(
            state,
            strict=False,  # Within the cyclic graph, violations flow to the circuit breaker
            sprint_days=sprint_days,
            points_per_day=points_per_day,
        )

    def _replan_step(state: SprintState) -> dict[str, Any]:
        return corrective_replan_node(
            state,
            sprint_days=sprint_days,
            points_per_day=points_per_day,
            enable_scope_trimming=enable_scope_trimming,
        )

    def _supervisor_step(state: SprintState) -> dict[str, Any]:
        return supervisor_node(
            state,
            llm=resolved_llm,
            strict=strict,
            sprint_days=sprint_days,
            points_per_day=points_per_day,
            sprint_goal=sprint_goal,
        )

    def _conditional_route(state: SprintState) -> str:
        return route_after_validation(state, max_retries=max_retries)

    builder = StateGraph(SprintState)
    builder.add_node("prioritizer", _prioritizer_step)
    builder.add_node("allocator", _allocator_step)
    builder.add_node("validator", _validator_step)
    builder.add_node("replan", _replan_step)
    builder.add_node("supervisor", _supervisor_step)

    builder.add_edge(START, "prioritizer")
    builder.add_edge("prioritizer", "allocator")
    builder.add_edge("allocator", "validator")
    builder.add_conditional_edges(
        "validator",
        _conditional_route,
        {
            "replan": "replan",
            "supervisor": "supervisor",
        },
    )
    builder.add_edge("replan", "allocator")
    builder.add_edge("supervisor", END)

    return builder.compile(checkpointer=checkpointer)


def run_sprint_planning(
    backlog: list[Union[Task, dict]],
    team: list[Union[DeveloperProfile, dict]],
    thread_id: str = "default",
    sprint_goal: str = "Deliver prioritized and feasible sprint backlog.",
    checkpointer: Optional[Any] = None,
    llm: Optional[BaseChatModel] = None,
    strict: bool = False,
    max_retries: int = 2,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
    enable_scope_trimming: bool = True,
    scenario_name: str = "custom",
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """High-level helper for end-to-end execution of the Sprint Planning MAS.

    Args:
        backlog: List of tasks to be planned.
        team: List of available developer profiles.
        thread_id: Session identifier for checkpointing.
        sprint_goal: Sprint objective.
        checkpointer: Optional memory checkpointer (default: None).
        llm: Optional custom LangChain chat model.
        strict: Strict validation mode.
        max_retries: Circuit breaker limit for corrective replanning passes (default: 2).
        sprint_days: Duration in business days (default: 10).
        points_per_day: Story points per full-time day (default: 2.0).
        enable_scope_trimming: Enables deterministic capacity-based scope trimming.
        scenario_name: Scenario identifier for LangSmith run_name and metadata (default: 'custom').
        tags: Optional list of custom LangSmith tags.
        metadata: Optional dictionary of custom LangSmith metadata.

    Returns:
        dict[str, Any]: Final consolidated SprintState dictionary.

    Raises:
        ValueError: If backlog/team are empty or numeric parameters are out of bounds.
    """
    if not backlog:
        raise ValueError("Backlog must be non-empty.")
    if not team:
        raise ValueError("Team must be non-empty.")
    if max_retries < 0 or max_retries > 10:
        raise ValueError(f"max_retries must be between 0 and 10, got {max_retries}.")
    if sprint_days <= 0:
        raise ValueError(f"sprint_days must be greater than 0, got {sprint_days}.")
    if points_per_day <= 0:
        raise ValueError(f"points_per_day must be greater than 0, got {points_per_day}.")

    tasks = [t if isinstance(t, Task) else Task(**t) for t in backlog]
    devs = [d if isinstance(d, DeveloperProfile) else DeveloperProfile(**d) for d in team]

    graph = build_sprint_graph(
        checkpointer=checkpointer,
        max_retries=max_retries,
        llm=llm,
        strict=strict,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
        enable_scope_trimming=enable_scope_trimming,
        sprint_goal=sprint_goal,
    )

    initial_state: SprintState = {
        "backlog": tasks,
        "team": devs,
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    config = build_langsmith_run_config(
        thread_id=thread_id,
        scenario_name=scenario_name,
        sprint_goal=sprint_goal,
        max_retries=max_retries,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
        tags=tags,
        metadata=metadata,
    )

    return graph.invoke(initial_state, config=config)
