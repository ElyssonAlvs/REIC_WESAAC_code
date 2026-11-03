"""Suíte de testes de integração ponta a ponta do Grafo LangGraph e Orquestração Cíclica (graph.py)."""

import concurrent.futures
import pytest

from sprint_mas.agents import deterministic_topological_sort
from sprint_mas.data_loader import load_scenario
from sprint_mas.graph import (
    build_sprint_graph,
    corrective_replan_node,
    create_memory_checkpointer,
    route_after_validation,
    run_sprint_planning,
    select_feasible_sprint_tasks,
)
from sprint_mas.state import Allocation, DeveloperProfile, SprintPlan, SprintState, Task
from sprint_mas.tools import calculate_team_capacity


def test_scenario_a_happy_path_one_pass():
    """Valida execução ponta a ponta do Cenário A: 1-pass direto, aprovação na 1ª passagem."""
    tasks, team = load_scenario("scenario_a")

    final_state = run_sprint_planning(
        backlog=tasks,
        team=team,
        thread_id="test_scenario_a",
        sprint_goal="Scenario A Happy Path Delivery",
        max_retries=2,
    )

    plan = final_state["sprint_plan"]
    assert plan is not None
    assert isinstance(plan, SprintPlan)
    assert plan.total_points == 35
    assert len(plan.tasks) == 10
    assert len(plan.allocations) == 10
    assert final_state["validation_errors"] == []

    # Verifica a sequência de mensagens: exatamente 1 passagem (sem nós de replan)
    msg_headers = [
        m.content.splitlines()[0].strip()
        for m in final_state["messages"]
        if getattr(m, "content", "")
    ]
    assert "### Prioritizer Agent Deliberation" in msg_headers[0]
    assert "### Allocator Agent Deliberation" in msg_headers[1]
    assert "### Validator Agent Deliberation" in msg_headers[2]
    assert "### Supervisor Agent Deliberation" in msg_headers[3]
    assert len(msg_headers) == 4


def test_scenario_b_subset_happy_path_one_pass():
    """Valida execução de um subconjunto viável do Cenário B (60 pts <= 84 pts, dev_D <= 10 pts)."""
    tasks_all, team = load_scenario("scenario_b")
    task_dict = {t.id: t for t in tasks_all}

    selected_ids = [
        "TSK-101", "TSK-102", "TSK-103", "TSK-104", "TSK-105",
        "TSK-106", "TSK-107", "TSK-108", "TSK-109", "TSK-111",
        "TSK-116", "TSK-121", "TSK-126",
    ]
    sprint_tasks = [task_dict[tid] for tid in selected_ids]

    final_state = run_sprint_planning(
        backlog=sprint_tasks,
        team=team,
        thread_id="test_scenario_b_subset",
        sprint_goal="Scenario B Subset Feasible Delivery",
        max_retries=2,
    )

    plan = final_state["sprint_plan"]
    assert plan is not None
    assert plan.total_points == 60
    assert len(plan.tasks) == 13
    assert final_state["validation_errors"] == []

    # Validação de tetos REIC 2026
    points_by_dev = {d.id: 0 for d in team}
    for a in plan.allocations:
        points_by_dev[a.developer_id] += a.allocated_points

    assert points_by_dev["dev_D"] <= 10.0
    assert points_by_dev["dev_B"] <= 14.0

    # Causalidade DAG: TSK-101 precede TSK-102
    task_order = [t.id for t in plan.tasks]
    assert task_order.index("TSK-101") < task_order.index("TSK-102")


def test_scenario_b_full_backlog_cyclic_replan_two_pass():
    """Valida Cenário B completo (30 tarefas = 128 pts > 84 pts) ativando o ciclo corretivo de replanejamento.

    Comportamento esperado:
    - Passagem 1: prioritizer (30 tarefas) -> allocator (128 pts) -> validator (estouro de FTE)
    - Condicional: route_after_validation detecta erro e roteia para corrective_replan_node
    - Replan: seleciona subconjunto viável (total_points <= 84, dev_D <= 10) e zera allocations
    - Passagem 2: allocator (re-aloca) -> validator (0 violações) -> supervisor (SprintPlan aprovado)
    """
    tasks_all, team = load_scenario("scenario_b")
    assert len(tasks_all) == 30
    assert sum(t.story_points for t in tasks_all) == 128

    final_state = run_sprint_planning(
        backlog=tasks_all,
        team=team,
        thread_id="test_scenario_b_full",
        sprint_goal="Scenario B Full Backlog with Scope Trimming",
        max_retries=2,
    )

    plan = final_state["sprint_plan"]
    assert plan is not None
    assert isinstance(plan, SprintPlan)
    assert plan.total_points <= 84
    assert plan.total_points == 66  # Tamanho ótimo determinístico para a equipe de 84 pts
    assert len(plan.tasks) == 15
    assert final_state["validation_errors"] == []

    # Validação dos tetos FTE por desenvolvedor
    points_by_dev = {d.id: 0 for d in team}
    for a in plan.allocations:
        points_by_dev[a.developer_id] += a.allocated_points

    assert points_by_dev["dev_D"] <= 10.0
    assert points_by_dev["dev_B"] <= 14.0
    assert points_by_dev["dev_C"] <= 20.0
    assert sum(points_by_dev.values()) <= 84.0

    # Rastreamento das deliberações das 2 passagens
    headers = [
        m.content.splitlines()[0].strip()
        for m in final_state["messages"]
        if getattr(m, "content", "")
    ]
    expected_headers = [
        "### Prioritizer Agent Deliberation",
        "### Allocator Agent Deliberation",
        "### Validator Agent Deliberation",
        "### Replan Agent Deliberation (Corrective Scope Trimming)",
        "### Allocator Agent Deliberation",
        "### Validator Agent Deliberation",
        "### Supervisor Agent Deliberation",
    ]
    assert headers == expected_headers


def test_circuit_breaker_terminates_unrecoverable_failure():
    """Valida que falha irrecuperável (enable_scope_trimming=False com sobrecarga) interrompe via circuit breaker.

    Garante zero risco de loop infinito (sem GraphRecursionError):
    - Realiza exatamente max_retries retentativas
    - Circuit breaker força o desvio para supervisor_node
    - Supervisor rejeita formalmente (sprint_plan=None e validation_errors preservados)
    """
    tasks_all, team = load_scenario("scenario_b")

    final_state = run_sprint_planning(
        backlog=tasks_all,
        team=team,
        thread_id="test_circuit_breaker",
        max_retries=2,
        enable_scope_trimming=False,  # Não permite corte, tornando o excesso de 128 pts irrecuperável
    )

    assert final_state["sprint_plan"] is None
    assert len(final_state["validation_errors"]) > 0

    # Contagem de tentativas do validador nas mensagens
    validator_headers = [
        m.content.splitlines()[0].strip()
        for m in final_state["messages"]
        if "### Validator Agent Deliberation" in getattr(m, "content", "")
    ]
    # Passagem 1 inicial + 2 retentativas = 3 validações
    assert len(validator_headers) == 3

    # Última mensagem deve ser do Supervisor rejeitando
    last_msg = str(final_state["messages"][-1].content)
    assert "### Supervisor Agent Deliberation" in last_msg
    assert "**Status**: REJECTED" in last_msg


def test_route_after_validation_bounds_and_conditions():
    """Valida o comportamento de route_after_validation sob diferentes estados e limites."""
    # max_retries inválido
    dummy_state: SprintState = {
        "backlog": [],
        "team": [],
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    with pytest.raises(ValueError):
        route_after_validation(dummy_state, max_retries=-1)
    with pytest.raises(ValueError):
        route_after_validation(dummy_state, max_retries=11)

    # Estado sem erros: sempre supervisor
    assert route_after_validation(dummy_state, max_retries=2) == "supervisor"

    # Estado com erros:
    error_state: SprintState = {
        **dummy_state,
        "validation_errors": ["Error 1"],
        "messages": [],
    }
    # max_retries=0: sem tentativas, vai direto ao supervisor
    assert route_after_validation(error_state, max_retries=0) == "supervisor"


def test_select_feasible_sprint_tasks_validation_guards():
    """Valida guardrails de parâmetros na função select_feasible_sprint_tasks."""
    tasks, team = load_scenario("scenario_a")
    with pytest.raises(ValueError):
        select_feasible_sprint_tasks([], team)
    with pytest.raises(ValueError):
        select_feasible_sprint_tasks(tasks, [])
    with pytest.raises(ValueError):
        select_feasible_sprint_tasks(tasks, team, sprint_days=0)
    with pytest.raises(ValueError):
        select_feasible_sprint_tasks(tasks, team, points_per_day=-1.0)


def test_memory_saver_checkpointing_session_isolation():
    """Valida que MemorySaver mantém isolamento estrito de snapshots entre diferentes thread_id."""
    tasks_a, team_a = load_scenario("scenario_a")
    tasks_b, team_b = load_scenario("scenario_b")

    checkpointer = create_memory_checkpointer()
    graph = build_sprint_graph(checkpointer=checkpointer)

    state_a: SprintState = {
        "backlog": tasks_a,
        "team": team_a,
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    state_b: SprintState = {
        "backlog": tasks_b[:5],  # 5 tarefas
        "team": team_b,
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    # Executa thread A
    res_a = graph.invoke(state_a, config={"configurable": {"thread_id": "session_A"}})
    # Executa thread B
    res_b = graph.invoke(state_b, config={"configurable": {"thread_id": "session_B"}})

    # Recupera snapshots independentes do checkpointer
    snap_a = graph.get_state(config={"configurable": {"thread_id": "session_A"}})
    snap_b = graph.get_state(config={"configurable": {"thread_id": "session_B"}})

    assert snap_a.values["sprint_plan"].total_points == 35
    assert len(snap_a.values["sprint_plan"].tasks) == 10

    assert len(snap_b.values["sprint_plan"].tasks) == 5
    assert snap_b.values["sprint_plan"].total_points != 35

    # Zero contaminação cruzada
    task_ids_a = {t.id for t in snap_a.values["sprint_plan"].tasks}
    task_ids_b = {t.id for t in snap_b.values["sprint_plan"].tasks}
    assert task_ids_a.isdisjoint(task_ids_b)


def test_parallel_concurrency_thread_pool_executor():
    """Valida que 10 execuções completas do grafo rodando em paralelo convergem deterministicamente."""
    tasks, team = load_scenario("scenario_a")

    def _worker(thread_num: int) -> int:
        local_tasks = [Task(**t.model_dump()) for t in tasks]
        local_team = [DeveloperProfile(**d.model_dump()) for d in team]

        result = run_sprint_planning(
            backlog=local_tasks,
            team=local_team,
            thread_id=f"concurrent_thread_{thread_num}",
            sprint_goal=f"Concurrent Sprint {thread_num}",
        )
        assert result["sprint_plan"] is not None
        assert result["validation_errors"] == []
        return result["sprint_plan"].total_points

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_worker, i) for i in range(10)]
        results = [f.result() for f in futures]

    assert len(results) == 10
    assert all(pts == 35 for pts in results)
