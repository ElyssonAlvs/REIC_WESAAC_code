"""Bateria de testes unitários para o Agente de Priorização (Product Owner Node)."""

import json
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage

from sprint_mas.agents import (
    PrioritizationOutput,
    deterministic_topological_sort,
    prioritization_node,
    prioritizer_node,
    validate_prioritization_order,
)
from sprint_mas.data_loader import load_scenario
from sprint_mas.state import SprintState, Task


def _make_mock_llm(output_payload: dict, wrap_markdown: bool = False) -> MagicMock:
    """Cria um mock de BaseChatModel retornando o payload serializado em JSON."""
    raw_json = json.dumps(output_payload)
    if wrap_markdown:
        content = f"```json\n{raw_json}\n```"
    else:
        content = raw_json
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=content)
    return mock_llm


def test_prioritization_node_scenario_a_happy_path():
    """Valida o nó de priorização no Cenário A com resposta válida simulada de LLM."""
    tasks, team = load_scenario("scenario_a")
    # Gera uma ordem causalmente válida usando o sort determinístico
    valid_ids = deterministic_topological_sort(tasks)

    mock_llm = _make_mock_llm({
        "prioritized_task_ids": valid_ids,
        "prioritization_reasoning": "Ordem priorizada com foco nas fundações de CI/CD e banco de dados.",
    })

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = prioritization_node(state, llm=mock_llm, strict=True)

    assert "prioritized_tasks" in result
    assert "messages" in result
    assert len(result["prioritized_tasks"]) == 10
    assert [t.id for t in result["prioritized_tasks"]] == valid_ids
    assert len(result["messages"]) == 1
    assert "Prioritizer Agent Deliberation" in result["messages"][0].content


def test_prioritization_node_scenario_b_causal_chains():
    """Valida que a priorização do Cenário B respeita rigorosamente as 5 cadeias causais do paper.

    Cadeias estritas do paper WESAAC 2025 / REIC 2026:
    - TSK-101 antecede TSK-102
    - TSK-104 antecede TSK-105
    - TSK-109 antecede TSK-110
    - TSK-114 antecede TSK-115
    - TSK-119 antecede TSK-120
    """
    tasks, team = load_scenario("scenario_b")
    valid_ids = deterministic_topological_sort(tasks)

    mock_llm = _make_mock_llm({
        "prioritized_task_ids": valid_ids,
        "prioritization_reasoning": "Priorização mitigando dependências críticas de mensageria e pagamento.",
    })

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = prioritization_node(state, llm=mock_llm, strict=True)
    p_tasks = result["prioritized_tasks"]
    assert len(p_tasks) == 30

    pos = {t.id: idx for idx, t in enumerate(p_tasks)}

    # Validação das 5 cadeias causais
    assert pos["TSK-101"] < pos["TSK-102"], "TSK-101 deve preceder TSK-102"
    assert pos["TSK-104"] < pos["TSK-105"], "TSK-104 deve preceder TSK-105"
    assert pos["TSK-109"] < pos["TSK-110"], "TSK-109 deve preceder TSK-110"
    assert pos["TSK-114"] < pos["TSK-115"], "TSK-114 deve preceder TSK-115"
    assert pos["TSK-119"] < pos["TSK-120"], "TSK-119 deve preceder TSK-120"


def test_deterministic_topological_sort_business_value():
    """Valida que tarefas prontas são desempatadas por priority (1 > 2 > 3) e story points (-sp)."""
    tasks = [
        Task(id="T-LOW", title="Low Prio", description="D", story_points=8, skill_required="backend", priority=5),
        Task(id="T-HIGH-SMALL", title="High Small", description="D", story_points=2, skill_required="backend", priority=1),
        Task(id="T-HIGH-BIG", title="High Big", description="D", story_points=8, skill_required="backend", priority=1),
        Task(id="T-MED", title="Med Prio", description="D", story_points=5, skill_required="backend", priority=3),
    ]

    ordered = deterministic_topological_sort(tasks)

    # Ambas têm prioridade 1, mas T-HIGH-BIG tem 8 pts vs 2 pts -> T-HIGH-BIG vem primeiro
    assert ordered[0] == "T-HIGH-BIG"
    assert ordered[1] == "T-HIGH-SMALL"
    # Prioridade 3 vem antes de prioridade 5
    assert ordered[2] == "T-MED"
    assert ordered[3] == "T-LOW"


def test_validate_prioritization_rejects_unknown_id_idor():
    """Garante que a presença de ID desconhecido na ordenação dispara ValueError (Anti-IDOR)."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=3, skill_required="backend", priority=1),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_prioritization_order(tasks, ["T1", "T_INTRUSO"])
    assert "Violação Anti-IDOR" in str(exc_info.value)
    assert "T_INTRUSO" in str(exc_info.value)


def test_validate_prioritization_rejects_missing_or_duplicate_tasks():
    """Garante que tarefas omitidas ou duplicadas disparam ValueError."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=3, skill_required="backend", priority=1),
        Task(id="T2", title="T2", description="D", story_points=3, skill_required="backend", priority=2),
    ]

    # Teste de duplicata
    with pytest.raises(ValueError) as exc_dup:
        validate_prioritization_order(tasks, ["T1", "T1"])
    assert "duplicadas" in str(exc_dup.value)

    # Teste de omissão
    with pytest.raises(ValueError) as exc_miss:
        validate_prioritization_order(tasks, ["T1"])
    assert "faltantes" in str(exc_miss.value)


def test_validate_prioritization_rejects_causal_inversion():
    """Garante que inversão causal (filho antes do pai) dispara ValueError explicativo."""
    tasks = [
        Task(id="TSK-101", title="Pai", description="D", story_points=5, skill_required="backend", priority=1),
        Task(id="TSK-102", title="Filho", description="D", story_points=5, skill_required="backend", priority=1, dependencies=["TSK-101"]),
    ]

    # Inversão: TSK-102 antes de TSK-101
    with pytest.raises(ValueError) as exc_info:
        validate_prioritization_order(tasks, ["TSK-102", "TSK-101"])
    assert "Inversão causal de dependência" in str(exc_info.value)
    assert "TSK-102" in str(exc_info.value)
    assert "TSK-101" in str(exc_info.value)


def test_prioritization_node_strict_mode_raises_on_violation():
    """Garante que com strict=True, saída inválida do LLM levanta ValueError."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=2, skill_required="backend", priority=1),
        Task(id="T2", title="T2", description="D", story_points=3, skill_required="backend", priority=1, dependencies=["T1"]),
    ]
    # LLM alucina invertendo a dependência
    mock_llm = _make_mock_llm({
        "prioritized_task_ids": ["T2", "T1"],
        "prioritization_reasoning": "Alucinação causal.",
    })

    state: SprintState = {
        "backlog": tasks,
        "team": [],
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    with pytest.raises(ValueError) as exc_info:
        prioritization_node(state, llm=mock_llm, strict=True)
    assert "Falha na validação da priorização do LLM (strict=True)" in str(exc_info.value)


def test_prioritization_node_resilient_fallback_on_bad_llm_output():
    """Garante que com strict=False, falha do LLM ativa fallback determinístico com 0% erro."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=2, skill_required="backend", priority=1),
        Task(id="T2", title="T2", description="D", story_points=3, skill_required="backend", priority=1, dependencies=["T1"]),
    ]
    # LLM retorna saída inválida com omissão
    mock_llm = _make_mock_llm({
        "prioritized_task_ids": ["T2"],
        "prioritization_reasoning": "Resposta incompleta.",
    })

    state: SprintState = {
        "backlog": tasks,
        "team": [],
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = prioritization_node(state, llm=mock_llm, strict=False)

    p_tasks = result["prioritized_tasks"]
    assert len(p_tasks) == 2
    # Fallback determinístico garante causalidade (T1 antes de T2)
    assert p_tasks[0].id == "T1"
    assert p_tasks[1].id == "T2"
    assert "Fallback Determinístico Ativado" in result["messages"][0].content


def test_prioritization_node_handles_markdown_code_fences():
    """Garante que o parser trata e remove markdown fences (```json ... ```) do LLM."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=2, skill_required="backend", priority=1),
    ]
    mock_llm = _make_mock_llm(
        {
            "prioritized_task_ids": ["T1"],
            "prioritization_reasoning": "Parse com markdown fences.",
        },
        wrap_markdown=True,
    )

    state: SprintState = {
        "backlog": tasks,
        "team": [],
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = prioritization_node(state, llm=mock_llm, strict=True)
    assert len(result["prioritized_tasks"]) == 1
    assert result["prioritized_tasks"][0].id == "T1"


def test_prioritization_node_empty_backlog_raises():
    """Garante que backlog vazio ou ausente dispara ValueError defensivo imediato."""
    state: SprintState = {
        "backlog": [],
        "team": [],
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    with pytest.raises(ValueError) as exc_info:
        prioritization_node(state)
    assert "backlog de tarefas está vazio ou ausente" in str(exc_info.value)


def test_prioritizer_node_alias():
    """Comprova que prioritizer_node é alias canônico de prioritization_node."""
    assert prioritizer_node is prioritization_node
