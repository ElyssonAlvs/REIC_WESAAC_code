"""Suíte de testes para o Agente Supervisor de Governança (Supervisor Node / supervisor.py)."""

import concurrent.futures
import json
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from sprint_mas.agents import (
    SupervisorOutput,
    deterministic_allocation,
    deterministic_supervisor_decision,
    deterministic_topological_sort,
    governance_supervisor_node,
    supervisor_node,
    validate_supervisor_decision,
)
from sprint_mas.agents.validator import audit_sprint_state
from sprint_mas.data_loader import load_scenario
from sprint_mas.state import Allocation, DeveloperProfile, SprintPlan, SprintState, Task


def _make_mock_llm(output_payload: dict, wrap_markdown: bool = False) -> MagicMock:
    """Cria um mock de BaseChatModel retornando o payload serializado em JSON."""
    raw_json = json.dumps(output_payload)
    content = f"```json\n{raw_json}\n```" if wrap_markdown else raw_json
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=content)
    return mock_llm


def _build_valid_scenario_a_state() -> SprintState:
    """Constrói um SprintState válido com base no Cenário A."""
    tasks, team = load_scenario("scenario_a")
    ordered_ids = deterministic_topological_sort(tasks)
    task_map = {t.id: t for t in tasks}
    prioritized_tasks = [task_map[tid] for tid in ordered_ids]
    allocations = deterministic_allocation(prioritized_tasks, team)

    return {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": prioritized_tasks,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }


def test_supervisor_output_schema_extra_forbid():
    """Valida que SupervisorOutput rejeita Mass Assignment (campos extras) via ConfigDict(extra='forbid')."""
    valid_payload = {
        "is_approved": True,
        "validation_errors": [],
        "sprint_summary": "All checks passed.",
        "recommendations": "Follow agile standards.",
    }
    output = SupervisorOutput(**valid_payload)
    assert output.is_approved is True
    assert output.validation_errors == []

    # Injeção de campo não autorizado
    hacked_payload = {
        **valid_payload,
        "admin_override": True,
    }
    with pytest.raises(ValidationError) as exc_info:
        SupervisorOutput(**hacked_payload)
    assert "extra_forbidden" in str(exc_info.value)


def test_deterministic_supervisor_decision_valid_and_invalid():
    """Valida deterministic_supervisor_decision para estados válidos e inválidos."""
    valid_state = _build_valid_scenario_a_state()
    valid_decision = deterministic_supervisor_decision(valid_state)
    assert valid_decision.is_approved is True
    assert valid_decision.validation_errors == []
    assert "Sprint plan approved" in valid_decision.sprint_summary

    # Cria estado inválido (carga adulterada com estouro de FTE)
    tasks = valid_state["prioritized_tasks"]
    team = valid_state["team"]
    tampered_allocs = [
        Allocation(
            task_id=t.id,
            developer_id=team[0].id,
            allocated_points=t.story_points,
            reason="All to dev 0",
        )
        for t in tasks
    ]
    invalid_state: SprintState = {
        **valid_state,
        "allocations": tampered_allocs,
    }
    invalid_decision = deterministic_supervisor_decision(invalid_state)
    assert invalid_decision.is_approved is False
    assert len(invalid_decision.validation_errors) > 0
    assert "Sprint plan rejected" in invalid_decision.sprint_summary


def test_validate_supervisor_decision_blocks_hallucination():
    """Valida que validate_supervisor_decision levanta ValueError se is_approved=True diante de violações."""
    valid_state = _build_valid_scenario_a_state()
    report = audit_sprint_state(valid_state)
    decision = SupervisorOutput(
        is_approved=True,
        validation_errors=[],
        sprint_summary="Ok",
        recommendations="Ok",
    )
    # Não deve levantar exceção para estado íntegro
    validate_supervisor_decision(valid_state, decision, report=report)

    # Estado com violação
    tampered_allocs = [
        Allocation(
            task_id=t.id,
            developer_id="ghost_dev",  # IDOR: dev inexistente
            allocated_points=t.story_points,
            reason="Ghost dev",
        )
        for t in valid_state["prioritized_tasks"]
    ]
    invalid_state: SprintState = {
        **valid_state,
        "allocations": tampered_allocs,
    }
    invalid_report = audit_sprint_state(invalid_state)
    assert not invalid_report.is_valid

    with pytest.raises(ValueError) as exc_info:
        validate_supervisor_decision(invalid_state, decision, report=invalid_report)
    assert "Server Authority violation" in str(exc_info.value)


def test_supervisor_node_scenario_a_happy_path_with_markdown_fences():
    """Valida o nó supervisor_node consolidando SprintPlan quando LLM aprova com markdown fences."""
    state = _build_valid_scenario_a_state()
    mock_llm = _make_mock_llm(
        {
            "is_approved": True,
            "validation_errors": [],
            "sprint_summary": "Sprint 1 audit complete. Feasibility verified.",
            "recommendations": "Keep daily standups focused on blockages.",
        },
        wrap_markdown=True,
    )

    result = supervisor_node(
        state=state,
        llm=mock_llm,
        strict=True,
        sprint_goal="Complete Scenario A MVP.",
    )

    assert "sprint_plan" in result
    plan = result["sprint_plan"]
    assert isinstance(plan, SprintPlan)
    assert plan.sprint_name == "Sprint 1"
    assert plan.sprint_goal == "Complete Scenario A MVP."
    assert plan.total_points == sum(t.story_points for t in state["prioritized_tasks"])
    assert len(plan.tasks) == 10
    assert len(plan.allocations) == 10
    assert result["validation_errors"] == []

    assert len(result["messages"]) == 1
    msg_content = str(result["messages"][0].content)
    assert "### Supervisor Agent Deliberation" in msg_content
    assert "**Status**: APPROVED" in msg_content


def test_supervisor_node_server_authority_recalculates_total_points():
    """Valida que o total_points do SprintPlan é SEMPRE recalculado pelos Task.story_points do servidor."""
    state = _build_valid_scenario_a_state()
    canonical_points = sum(t.story_points for t in state["prioritized_tasks"])

    mock_llm = _make_mock_llm(
        {
            "is_approved": True,
            "validation_errors": [],
            "sprint_summary": "LLM claims 999 points were planned.",
            "recommendations": "Ignore hallucinated points.",
        }
    )

    result = supervisor_node(state=state, llm=mock_llm, strict=True)
    plan = result["sprint_plan"]
    assert plan is not None
    # Deve ser 35 pontos canônicos, nunca 999
    assert plan.total_points == canonical_points == 35


def test_supervisor_node_blocks_hallucinated_approval_strict_and_fallback():
    """Valida bloqueio de alucinação de aprovação: ValueError em strict=True e rejeição segura em strict=False."""
    valid_state = _build_valid_scenario_a_state()
    # Adulterar para criar violação de IDOR
    invalid_state: SprintState = {
        **valid_state,
        "allocations": [
            Allocation(
                task_id=valid_state["prioritized_tasks"][0].id,
                developer_id="unregistered_developer_x",
                allocated_points=3,
                reason="Invalid allocation",
            )
        ],
    }

    # LLM alucina que está tudo aprovado
    hallucinating_llm = _make_mock_llm(
        {
            "is_approved": True,
            "validation_errors": [],
            "sprint_summary": "Everything looks fine to me!",
            "recommendations": "Ship it.",
        }
    )

    # 1. Com strict=True: deve levantar ValueError impedindo aprovação
    with pytest.raises(ValueError) as exc_info:
        supervisor_node(invalid_state, llm=hallucinating_llm, strict=True)
    assert "Server Authority violation" in str(exc_info.value) or "Supervisor deliberation failed" in str(exc_info.value)

    # 2. Com strict=False: guardião veta e converte para rejeição determinística segura
    result = supervisor_node(invalid_state, llm=hallucinating_llm, strict=False)
    assert result["sprint_plan"] is None
    assert len(result["validation_errors"]) > 0
    assert "unregistered_developer_x" in " ".join(result["validation_errors"])
    assert "**Status**: REJECTED" in str(result["messages"][0].content)


def test_supervisor_node_mass_assignment_extra_fields():
    """Valida rejeição de payload com campos extras injetados (Mass Assignment)."""
    state = _build_valid_scenario_a_state()
    hacked_llm = _make_mock_llm(
        {
            "is_approved": True,
            "validation_errors": [],
            "sprint_summary": "Normal summary.",
            "recommendations": "Normal recs.",
            "escalate_privileges": True,  # Campo não autorizado
        }
    )

    with pytest.raises(ValueError) as exc_info:
        supervisor_node(state, llm=hacked_llm, strict=True)
    assert "extra_forbidden" in str(exc_info.value) or "deliberation failed" in str(exc_info.value)

    # Em strict=False, aplica fallback determinístico íntegro
    res = supervisor_node(state, llm=hacked_llm, strict=False)
    assert res["sprint_plan"] is not None
    assert res["sprint_plan"].total_points == 35


def test_supervisor_node_alias_identity():
    """Valida que governance_supervisor_node é alias exato de supervisor_node."""
    assert governance_supervisor_node is supervisor_node


def test_supervisor_node_thread_safety_concurrency():
    """Valida execução simultânea de 10 chamadas ao supervisor_node sem race conditions."""
    state = _build_valid_scenario_a_state()
    mock_llm = _make_mock_llm(
        {
            "is_approved": True,
            "validation_errors": [],
            "sprint_summary": "Concurrent execution verified.",
            "recommendations": "Thread-safety assured.",
        }
    )

    def _worker(thread_idx: int) -> int:
        local_state = dict(state)
        local_state["messages"] = []
        res = supervisor_node(
            state=local_state,
            llm=mock_llm,
            strict=True,
            sprint_goal=f"Goal for thread {thread_idx}",
        )
        assert res["sprint_plan"] is not None
        assert res["sprint_plan"].total_points == 35
        return res["sprint_plan"].total_points

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_worker, i) for i in range(10)]
        results = [f.result() for f in futures]

    assert len(results) == 10
    assert all(pts == 35 for pts in results)
