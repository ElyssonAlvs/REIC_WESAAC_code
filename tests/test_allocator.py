"""Bateria de testes unitários para o Agente de Alocação de Recursos (Allocator Node)."""

import json
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage

from sprint_mas.agents import (
    AllocationItem,
    AllocationOutput,
    allocation_node,
    allocator_node,
    deterministic_allocation,
    validate_allocation_plan,
)
from sprint_mas.data_loader import load_scenario
from sprint_mas.state import Allocation, DeveloperProfile, SprintState, Task


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


def test_allocation_node_scenario_a_happy_path():
    """Valida o nó de alocação no Cenário A com resposta simulada válida de LLM."""
    tasks, team = load_scenario("scenario_a")
    valid_allocs = deterministic_allocation(tasks, team)

    payload = {
        "allocations": [
            {
                "task_id": a.task_id,
                "developer_id": a.developer_id,
                "allocated_points": a.allocated_points,
                "reason": a.reason,
            }
            for a in valid_allocs
        ],
        "allocation_summary": "Alocação balanceada do Cenário A respeitando competências e capacidades.",
    }
    mock_llm = _make_mock_llm(payload)

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = allocation_node(state, llm=mock_llm, strict=True)

    assert "allocations" in result
    assert "messages" in result
    assert len(result["allocations"]) == len(tasks)
    assert len(result["messages"]) == 1
    assert "Allocator Agent Deliberation" in result["messages"][0].content


def test_allocation_node_scenario_b_fte_and_bottleneck():
    """Valida que no Cenário B dev_D respeita <= 10 pts e dev_C (Fullstack) absorve backend."""
    tasks_all, team = load_scenario("scenario_b")
    task_dict = {t.id: t for t in tasks_all}

    # Seleciona conjunto de tarefas do Cenário B com forte concentração de backend
    # Total de 60 pontos, com 42 pontos de backend (excedendo os 24 pts de dev_B + dev_D)
    selected_ids = [
        "TSK-101", "TSK-102", "TSK-103", "TSK-104", "TSK-105",
        "TSK-106", "TSK-107", "TSK-108", "TSK-109", "TSK-111",
        "TSK-116", "TSK-121", "TSK-126",
    ]
    sprint_tasks = [task_dict[tid] for tid in selected_ids]
    valid_allocs = deterministic_allocation(sprint_tasks, team)

    payload = {
        "allocations": [
            {
                "task_id": a.task_id,
                "developer_id": a.developer_id,
                "allocated_points": a.allocated_points,
                "reason": a.reason,
            }
            for a in valid_allocs
        ],
        "allocation_summary": "Mitigação do gargalo de backend via dev_C e teto rígido de 0.5 FTE no dev_D.",
    }
    mock_llm = _make_mock_llm(payload)

    state: SprintState = {
        "backlog": sprint_tasks,
        "team": team,
        "prioritized_tasks": sprint_tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = allocation_node(state, llm=mock_llm, strict=True)
    allocs = result["allocations"]
    assert len(allocs) == len(sprint_tasks)

    # Verifica teto do dev_D (<= 10 pontos)
    dev_d_points = sum(a.allocated_points for a in allocs if a.developer_id == "dev_D")
    assert dev_d_points <= 10.0, f"dev_D não pode receber mais de 10 pts. Recebeu {dev_d_points}"

    # Verifica se dev_C absorveu tarefas de backend
    task_map = {t.id: t for t in sprint_tasks}
    dev_c_backend = [
        a for a in allocs
        if a.developer_id == "dev_C" and task_map[a.task_id].skill_required == "backend"
    ]
    assert len(dev_c_backend) > 0, "dev_C (Fullstack) deve absorver tarefas de backend para mitigar o gargalo"


def test_deterministic_allocation_scenario_b_validity():
    """Valida execução direta do algoritmo determinístico no Cenário B com conformidade estrita."""
    tasks_all, team = load_scenario("scenario_b")
    task_dict = {t.id: t for t in tasks_all}

    selected_ids = [
        "TSK-101", "TSK-102", "TSK-103", "TSK-104", "TSK-105",
        "TSK-106", "TSK-107", "TSK-108", "TSK-109", "TSK-111",
        "TSK-116", "TSK-121", "TSK-126",
    ]
    sprint_tasks = [task_dict[tid] for tid in selected_ids]

    allocations = deterministic_allocation(sprint_tasks, team)

    # Não deve levantar nenhuma exceção
    validate_allocation_plan(sprint_tasks, team, allocations)

    # dev_D não pode exceder 10 pontos
    dev_d_points = sum(a.allocated_points for a in allocations if a.developer_id == "dev_D")
    assert dev_d_points <= 10.0

    # dev_B não pode exceder 14 pontos
    dev_b_points = sum(a.allocated_points for a in allocations if a.developer_id == "dev_B")
    assert dev_b_points <= 14.0

    # dev_C absorveu backend
    task_map = {t.id: t for t in sprint_tasks}
    dev_c_backend = [
        a for a in allocations
        if a.developer_id == "dev_C" and task_map[a.task_id].skill_required == "backend"
    ]
    assert len(dev_c_backend) > 0


def test_validate_allocation_rejects_unknown_dev_idor():
    """Garante rejeição Anti-IDOR quando um developer_id forjado é submetido."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=3, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_A", name="Alice", skills=["backend"], fte=1.0),
    ]
    bad_allocations = [
        Allocation(task_id="T1", developer_id="dev_Hacker", allocated_points=3, reason="Invasão"),
    ]

    with pytest.raises(ValueError) as exc_info:
        validate_allocation_plan(tasks, team, bad_allocations)
    assert "Violação Anti-IDOR" in str(exc_info.value)
    assert "dev_Hacker" in str(exc_info.value)


def test_validate_allocation_rejects_unknown_task_idor():
    """Garante rejeição Anti-IDOR quando um task_id forjado é submetido."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=3, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_A", name="Alice", skills=["backend"], fte=1.0),
    ]
    bad_allocations = [
        Allocation(task_id="TSK-INEXISTENTE", developer_id="dev_A", allocated_points=3, reason="ID forjado"),
    ]

    with pytest.raises(ValueError) as exc_info:
        validate_allocation_plan(tasks, team, bad_allocations)
    assert "Violação Anti-IDOR" in str(exc_info.value)
    assert "TSK-INEXISTENTE" in str(exc_info.value)


def test_validate_allocation_rejects_skill_mismatch():
    """Garante rejeição quando uma tarefa de backend é atribuída a desenvolvedor exclusivo de frontend."""
    tasks = [
        Task(id="T1", title="API Core", description="D", story_points=5, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_A", name="Alice", skills=["frontend", "ui"], fte=1.0),
    ]
    bad_allocations = [
        Allocation(task_id="T1", developer_id="dev_A", allocated_points=5, reason="Tentativa incompatível"),
    ]

    with pytest.raises(ValueError) as exc_info:
        validate_allocation_plan(tasks, team, bad_allocations)
    assert "Incompatibilidade de competência técnica" in str(exc_info.value)
    assert "dev_A" in str(exc_info.value)
    assert "backend" in str(exc_info.value)


def test_validate_allocation_rejects_fte_overload_dev_d():
    """Garante rejeição quando dev_D (0.5 FTE = 10 pts) recebe 15 pontos."""
    tasks = [
        Task(id="T1", title="API 1", description="D", story_points=8, skill_required="backend", priority=1),
        Task(id="T2", title="API 2", description="D", story_points=7, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_D", name="David", skills=["backend"], fte=0.5),  # 0.5 * 10 * 2 = 10 pts
    ]
    bad_allocations = [
        Allocation(task_id="T1", developer_id="dev_D", allocated_points=8, reason="API 1"),
        Allocation(task_id="T2", developer_id="dev_D", allocated_points=7, reason="API 2"),
    ]

    with pytest.raises(ValueError) as exc_info:
        validate_allocation_plan(tasks, team, bad_allocations)
    assert "Estouro de capacidade FTE" in str(exc_info.value)
    assert "dev_D" in str(exc_info.value)
    assert "15" in str(exc_info.value)


def test_validate_allocation_rejects_missing_or_duplicate_allocations():
    """Garante rejeição de propostas com tarefas duplicadas ou omitidas."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=3, skill_required="backend", priority=1),
        Task(id="T2", title="T2", description="D", story_points=3, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_B", name="Bob", skills=["backend"], fte=1.0),
    ]

    # Duplicata
    dup_allocations = [
        Allocation(task_id="T1", developer_id="dev_B", allocated_points=3, reason="R1"),
        Allocation(task_id="T1", developer_id="dev_B", allocated_points=3, reason="R2"),
    ]
    with pytest.raises(ValueError) as exc_dup:
        validate_allocation_plan(tasks, team, dup_allocations)
    assert "Tarefas duplicadas" in str(exc_dup.value)

    # Omissão (T2 esquecida)
    miss_allocations = [
        Allocation(task_id="T1", developer_id="dev_B", allocated_points=3, reason="R1"),
    ]
    with pytest.raises(ValueError) as exc_miss:
        validate_allocation_plan(tasks, team, miss_allocations)
    assert "Tarefas faltantes" in str(exc_miss.value)


def test_allocation_node_strict_mode_raises_on_violation():
    """Garante que com strict=True uma saída alucinada do LLM levanta ValueError."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=5, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_A", name="Alice", skills=["frontend"], fte=1.0),
    ]
    # LLM alucina alocando backend para dev exclusivo de frontend
    mock_llm = _make_mock_llm({
        "allocations": [
            {
                "task_id": "T1",
                "developer_id": "dev_A",
                "allocated_points": 5,
                "reason": "Alucinação de skill.",
            }
        ],
        "allocation_summary": "Plano falho.",
    })

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    with pytest.raises(ValueError) as exc_info:
        allocation_node(state, llm=mock_llm, strict=True)
    assert "Falha na validação do plano de alocação do LLM (strict=True)" in str(exc_info.value)


def test_allocation_node_resilient_fallback_on_bad_llm_output():
    """Garante que com strict=False uma falha do LLM ativa o fallback determinístico seguro."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=5, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_B", name="Bob", skills=["backend"], fte=1.0),
    ]
    # LLM retorna JSON corrompido / incompleto
    mock_llm = _make_mock_llm({
        "allocations": [],
        "allocation_summary": "Vazio",
    })

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = allocation_node(state, llm=mock_llm, strict=False)

    assert len(result["allocations"]) == 1
    assert result["allocations"][0].task_id == "T1"
    assert result["allocations"][0].developer_id == "dev_B"
    assert "[Fallback Determinístico Ativado]" in result["messages"][0].content


def test_allocation_node_handles_markdown_code_fences():
    """Garante que o nó extrai e valida JSON encapsulado em cercas markdown (```json ... ```)."""
    tasks = [
        Task(id="T1", title="T1", description="D", story_points=3, skill_required="backend", priority=1),
    ]
    team = [
        DeveloperProfile(id="dev_B", name="Bob", skills=["backend"], fte=1.0),
    ]
    payload = {
        "allocations": [
            {
                "task_id": "T1",
                "developer_id": "dev_B",
                "allocated_points": 3,
                "reason": "Alocação válida com cercas.",
            }
        ],
        "allocation_summary": "Alocação encapsulada em markdown.",
    }
    mock_llm = _make_mock_llm(payload, wrap_markdown=True)

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    result = allocation_node(state, llm=mock_llm, strict=True)
    assert len(result["allocations"]) == 1
    assert result["allocations"][0].task_id == "T1"


def test_allocation_node_empty_inputs_raises():
    """Garante que entradas vazias disparam ValueError defensivo imediato."""
    state_no_tasks: SprintState = {
        "backlog": [],
        "team": [DeveloperProfile(id="dev_A", name="A", skills=["backend"], fte=1.0)],
        "prioritized_tasks": [],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    with pytest.raises(ValueError) as exc_tasks:
        allocation_node(state_no_tasks)
    assert "Entradas inválidas para alocação" in str(exc_tasks.value)

    state_no_team: SprintState = {
        "backlog": [Task(id="T1", title="T", description="D", story_points=3, skill_required="backend", priority=1)],
        "team": [],
        "prioritized_tasks": [Task(id="T1", title="T", description="D", story_points=3, skill_required="backend", priority=1)],
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    with pytest.raises(ValueError) as exc_team:
        allocation_node(state_no_team)
    assert "Entradas inválidas para alocação" in str(exc_team.value)


def test_allocator_node_alias():
    """Comprova que allocator_node é alias canônico de allocation_node."""
    assert allocator_node is allocation_node
