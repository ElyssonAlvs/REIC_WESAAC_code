"""Suíte de testes para o Agente Validador Determinístico (Validator Node / validation_node)."""

import concurrent.futures
import pytest

from sprint_mas.agents import (
    ValidationReport,
    audit_sprint_state,
    deterministic_allocation,
    deterministic_topological_sort,
    validation_node,
    validator_node,
)
from sprint_mas.data_loader import load_scenario
from sprint_mas.state import Allocation, DeveloperProfile, SprintState, Task


def test_scenario_a_happy_path_validation():
    """Valida o plano do Cenário A com priorização topológica válida e alocações dentro de 1.0 FTE."""
    tasks, team = load_scenario("scenario_a")
    ordered_ids = deterministic_topological_sort(tasks)
    task_map = {t.id: t for t in tasks}
    prioritized_tasks = [task_map[tid] for tid in ordered_ids]
    allocations = deterministic_allocation(prioritized_tasks, team)

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": prioritized_tasks,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is True
    assert report.is_feasible is True
    assert report.violations == []
    assert len(report.allocated_by_dev) == len(team)

    node_res = validation_node(state)
    assert node_res["validation_errors"] == []
    assert len(node_res["messages"]) == 1
    assert "APPROVED" in str(node_res["messages"][0].content)


def test_scenario_b_happy_path_validation():
    """Valida o plano do Cenário B respeitando dev_D <= 10 pts, dev_B <= 14 pts e ordem causal TSK-101 -> TSK-102."""
    tasks_all, team = load_scenario("scenario_b")
    task_dict = {t.id: t for t in tasks_all}

    # Conjunto canônico da sprint do Cenário B (60 pts totais, resolvendo gargalo via dev_C)
    selected_ids = [
        "TSK-101", "TSK-102", "TSK-103", "TSK-104", "TSK-105",
        "TSK-106", "TSK-107", "TSK-108", "TSK-109", "TSK-111",
        "TSK-116", "TSK-121", "TSK-126",
    ]
    sprint_tasks = [task_dict[tid] for tid in selected_ids]

    ordered_ids = deterministic_topological_sort(sprint_tasks)
    sprint_task_map = {t.id: t for t in sprint_tasks}
    prioritized_tasks = [sprint_task_map[tid] for tid in ordered_ids]
    allocations = deterministic_allocation(prioritized_tasks, team)

    state: SprintState = {
        "backlog": sprint_tasks,
        "team": team,
        "prioritized_tasks": prioritized_tasks,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is True
    assert report.is_feasible is True
    assert report.violations == []

    # Strict compliance with REIC 2026 ceilings
    assert report.allocated_by_dev["dev_D"] <= 10.0
    assert report.allocated_by_dev["dev_B"] <= 14.0

    # dev_C absorveu backend mitigando gargalo estrutural
    dev_c_backend_tasks = [
        a.task_id for a in allocations
        if a.developer_id == "dev_C" and sprint_task_map[a.task_id].skill_required == "backend"
    ]
    assert len(dev_c_backend_tasks) > 0

    # Causalidade DAG: TSK-101 precede TSK-102
    pos_map = {t.id: idx for idx, t in enumerate(prioritized_tasks)}
    assert pos_map["TSK-101"] < pos_map["TSK-102"]

    node_res = validation_node(state)
    assert node_res["validation_errors"] == []
    assert "APPROVED" in str(node_res["messages"][0].content)


def test_idempotency_clearing_previous_errors():
    """Garante idempotência do loop: limpa validation_errors retornando lista vazia sem mutar state in-place."""
    tasks, team = load_scenario("scenario_a")
    ordered_ids = deterministic_topological_sort(tasks)
    task_map = {t.id: t for t in tasks}
    prioritized_tasks = [task_map[tid] for tid in ordered_ids]
    allocations = deterministic_allocation(prioritized_tasks, team)

    previous_errors = ["Erro de iteração prévia 1", "Erro de iteração prévia 2"]
    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": prioritized_tasks,
        "allocations": allocations,
        "validation_errors": list(previous_errors),
        "sprint_plan": None,
        "messages": [],
    }

    node_res = validation_node(state)
    assert node_res["validation_errors"] == []
    # Immutability check: state original permanece intacto
    assert state["validation_errors"] == previous_errors


def test_causal_dag_inversion_detected():
    """Detecta inversão causal de DAG quando uma tarefa filha aparece antes de seu predecessor."""
    tasks, team = load_scenario("scenario_b")
    task_map = {t.id: t for t in tasks}

    # Inverte TSK-102 (filha) antes de TSK-101 (pai)
    inverted_tasks = [task_map["TSK-102"], task_map["TSK-101"]] + [
        t for t in tasks if t.id not in ("TSK-101", "TSK-102")
    ]
    allocations = deterministic_allocation(inverted_tasks, team)

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": inverted_tasks,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert any(
        "TSK-102" in v and "TSK-101" in v and "causal" in v.lower()
        for v in report.violations
    )


def test_unscheduled_parent_dependency_detected():
    """Detecta violação quando tarefa alocada depende de pai que não foi agendado na sprint."""
    tasks, team = load_scenario("scenario_b")
    # TSK-102 depende de TSK-101. Omitimos TSK-101 da sprint.
    tasks_without_101 = [t for t in tasks if t.id != "TSK-101"]
    allocations = [
        Allocation(
            task_id=t.id,
            developer_id="dev_C",
            allocated_points=t.story_points,
            reason="test allocation",
        )
        for t in tasks_without_101
    ]

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks_without_101,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert any(
        "TSK-102" in v and "TSK-101" in v and "unscheduled" in v.lower()
        for v in report.violations
    )


def test_topological_circular_and_orphan_dependencies():
    """Detecta dependência órfã (pai inexistente) e ciclo de dependência circular no DAG."""
    team = [DeveloperProfile(id="dev_1", name="Dev 1", skills=["backend"], fte=1.0)]

    # 1. Dependência Órfã
    orphan_task = Task(
        id="TSK-A",
        title="Orphan Task",
        description="Task with non-existent parent",
        story_points=3,
        skill_required="backend",
        priority=1,
        dependencies=["TSK-GHOST-999"],
    )
    alloc_orphan = [
        Allocation(
            task_id="TSK-A",
            developer_id="dev_1",
            allocated_points=3,
            reason="orphan test",
        )
    ]
    state_orphan: SprintState = {
        "backlog": [orphan_task],
        "team": team,
        "prioritized_tasks": [orphan_task],
        "allocations": alloc_orphan,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    report_orphan = audit_sprint_state(state_orphan)
    assert report_orphan.is_valid is False
    assert any(
        "orphan" in v.lower() and "TSK-GHOST-999" in v
        for v in report_orphan.violations
    )

    # 2. Ciclo Circular
    c1 = Task(
        id="TSK-C1",
        title="C1",
        description="Cycle 1",
        story_points=2,
        skill_required="backend",
        priority=1,
        dependencies=["TSK-C2"],
    )
    c2 = Task(
        id="TSK-C2",
        title="C2",
        description="Cycle 2",
        story_points=2,
        skill_required="backend",
        priority=1,
        dependencies=["TSK-C1"],
    )
    alloc_cycle = [
        Allocation(task_id="TSK-C1", developer_id="dev_1", allocated_points=2, reason="cycle 1"),
        Allocation(task_id="TSK-C2", developer_id="dev_1", allocated_points=2, reason="cycle 2"),
    ]
    state_cycle: SprintState = {
        "backlog": [c1, c2],
        "team": team,
        "prioritized_tasks": [c1, c2],
        "allocations": alloc_cycle,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    report_cycle = audit_sprint_state(state_cycle)
    assert report_cycle.is_valid is False
    assert any(
        "circular" in v.lower() and "TSK-C1" in v
        for v in report_cycle.violations
    )


def test_skill_mismatch_detected():
    """Detecta violação de incompatibilidade de skill quando dev exclusivo frontend recebe backend."""
    tasks, team = load_scenario("scenario_a")
    backend_task = next(t for t in tasks if t.skill_required.lower() == "backend")

    allocations = deterministic_allocation(tasks, team)
    tampered_allocations = []
    for a in allocations:
        if a.task_id == backend_task.id:
            # dev_A é frontend estrito
            tampered_allocations.append(
                Allocation(
                    task_id=a.task_id,
                    developer_id="dev_A",
                    allocated_points=a.allocated_points,
                    reason="tampered frontend dev for backend task",
                )
            )
        else:
            tampered_allocations.append(a)

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": tampered_allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert any(
        "skill mismatch" in v.lower() and "dev_A" in v
        for v in report.violations
    )


def test_multi_error_collection_without_early_exit():
    """Garante coleta multi-erros acumulando violações de IDOR, skill, FTE e DAG na mesma passagem."""
    tasks, team = load_scenario("scenario_b")
    task_map = {t.id: t for t in tasks}

    # 1. Inversão DAG
    inverted_tasks = [task_map["TSK-102"], task_map["TSK-101"]] + [
        t for t in tasks if t.id not in ("TSK-101", "TSK-102")
    ]

    # 2. IDOR, 3. Skill mismatch, 4. Adulteração de story points, 5. Estouro de FTE
    multi_allocations = [
        # Skill mismatch: dev_A (frontend) recebe backend
        Allocation(
            task_id="TSK-101",
            developer_id="dev_A",
            allocated_points=task_map["TSK-101"].story_points,
            reason="skill mismatch",
        ),
        # Anti-IDOR: dev_Hacker não existe na equipe
        Allocation(
            task_id="TSK-102",
            developer_id="dev_Hacker",
            allocated_points=task_map["TSK-102"].story_points,
            reason="idor dev",
        ),
        # Adulteração de story points: alega 1 pt para tarefa de 8 pts
        Allocation(
            task_id="TSK-103",
            developer_id="dev_D",
            allocated_points=1,
            reason="tampered story points",
        ),
        # Estouro de FTE dev_D: 8 pts reais de TSK-103 + 8 pts de TSK-104 = 16 pts > 10.0
        Allocation(
            task_id="TSK-104",
            developer_id="dev_D",
            allocated_points=task_map["TSK-104"].story_points,
            reason="overload dev_D",
        ),
    ]
    for t in inverted_tasks[4:]:
        multi_allocations.append(
            Allocation(
                task_id=t.id,
                developer_id="dev_C",
                allocated_points=t.story_points,
                reason="rest",
            )
        )

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": inverted_tasks,
        "allocations": multi_allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert len(report.violations) >= 5

    # Validação da presença simultânea de todas as categorias
    assert any("causal" in v.lower() for v in report.violations)
    assert any("anti-idor" in v.lower() and "dev_hacker" in v.lower() for v in report.violations)
    assert any("skill mismatch" in v.lower() and "dev_a" in v.lower() for v in report.violations)
    assert any("tampering" in v.lower() and "TSK-103" in v for v in report.violations)
    assert any("fte capacity overflow" in v.lower() and "dev_d" in v.lower() for v in report.violations)


def test_fte_capacity_overflow():
    """Detecta estouro de teto analítico de FTE para dev_D (> 10 pts) e dev_B (> 14 pts)."""
    tasks, team = load_scenario("scenario_b")

    allocations = [
        # dev_D recebe 11 pts (TSK-104: 8 pts + TSK-105: 3 pts) -> Teto dev_D é 10.0 pts
        Allocation(task_id="TSK-104", developer_id="dev_D", allocated_points=8, reason="overload D1"),
        Allocation(task_id="TSK-105", developer_id="dev_D", allocated_points=3, reason="overload D2"),
        # dev_B recebe 18 pts (TSK-101: 5 pts + TSK-102: 5 pts + TSK-103: 8 pts) -> Teto dev_B é 14.0 pts
        Allocation(task_id="TSK-101", developer_id="dev_B", allocated_points=5, reason="overload B1"),
        Allocation(task_id="TSK-102", developer_id="dev_B", allocated_points=5, reason="overload B2"),
        Allocation(task_id="TSK-103", developer_id="dev_B", allocated_points=8, reason="overload B3"),
    ]
    for t in tasks:
        if t.id not in ("TSK-101", "TSK-102", "TSK-103", "TSK-104", "TSK-105"):
            allocations.append(
                Allocation(task_id=t.id, developer_id="dev_C", allocated_points=t.story_points, reason="test")
            )

    ordered_ids = deterministic_topological_sort(tasks)
    task_map = {t.id: t for t in tasks}
    prioritized_tasks = [task_map[tid] for tid in ordered_ids]

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": prioritized_tasks,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert any("fte capacity overflow" in v.lower() and "dev_D" in v for v in report.violations)
    assert any("fte capacity overflow" in v.lower() and "dev_B" in v for v in report.violations)


def test_story_points_tampering_and_server_authority():
    """Detecta adulteração de story points e recalcula a sobrecarga via Server Authority."""
    team = [DeveloperProfile(id="dev_D", name="Dev D", skills=["backend"], fte=0.5)]  # Teto: 10.0 pts
    t1 = Task(id="TSK-1", title="T1", description="D1", story_points=5, skill_required="backend", priority=1)
    t2 = Task(id="TSK-2", title="T2", description="D2", story_points=8, skill_required="backend", priority=2)

    # Fraude: alocação alega 1 pt em vez dos 8 pts canônicos
    allocations = [
        Allocation(task_id="TSK-1", developer_id="dev_D", allocated_points=5, reason="ok"),
        Allocation(task_id="TSK-2", developer_id="dev_D", allocated_points=1, reason="fraud"),
    ]

    state: SprintState = {
        "backlog": [t1, t2],
        "team": team,
        "prioritized_tasks": [t1, t2],
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    # Detecta adulteração
    assert any("tampering" in v.lower() and "TSK-2" in v for v in report.violations)
    # Server authority soma 5 + 8 = 13 pts (e não 5 + 1 = 6 pts)
    assert report.allocated_by_dev["dev_D"] == 13
    # Com 13 pts, estoura o teto de 10.0 pts do dev_D
    assert any("fte capacity overflow" in v.lower() and "dev_D" in v for v in report.violations)


def test_completeness_uniqueness_and_empty_allocations():
    """Detecta alocações vazias, tarefas omitidas e tarefas duplicadas na alocação."""
    tasks, team = load_scenario("scenario_a")

    # 1. Alocações vazias
    state_empty: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    report_empty = audit_sprint_state(state_empty)
    assert report_empty.is_valid is False
    assert any("allocations list is empty" in v.lower() for v in report_empty.violations)

    # 2. Tarefa faltante (omissão)
    valid_allocs = deterministic_allocation(tasks, team)
    state_missing: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": valid_allocs[:-1],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    report_missing = audit_sprint_state(state_missing)
    assert report_missing.is_valid is False
    assert any(
        "completeness violation" in v.lower() and valid_allocs[-1].task_id in v
        for v in report_missing.violations
    )

    # 3. Tarefa duplicada (mesma tarefa alocada 2 vezes)
    duplicate_alloc = Allocation(
        task_id=valid_allocs[0].task_id,
        developer_id=team[-1].id,
        allocated_points=valid_allocs[0].allocated_points,
        reason="duplicate allocation",
    )
    state_dup: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": valid_allocs + [duplicate_alloc],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }
    report_dup = audit_sprint_state(state_dup)
    assert report_dup.is_valid is False
    assert any(
        "uniqueness violation" in v.lower() and valid_allocs[0].task_id in v
        for v in report_dup.violations
    )


def test_invalid_parameters_raise_value_error():
    """Levanta ValueError imediato diante de parâmetros ou entradas vazias/inválidas."""
    tasks, team = load_scenario("scenario_a")
    valid_state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    # sprint_days <= 0
    with pytest.raises(ValueError, match="sprint_days must be greater than 0"):
        audit_sprint_state(valid_state, sprint_days=0)
    with pytest.raises(ValueError, match="sprint_days must be greater than 0"):
        validation_node(valid_state, sprint_days=-5)

    # points_per_day <= 0
    with pytest.raises(ValueError, match="points_per_day must be greater than 0"):
        audit_sprint_state(valid_state, points_per_day=0.0)
    with pytest.raises(ValueError, match="points_per_day must be greater than 0"):
        validation_node(valid_state, points_per_day=-1.0)

    # Time vazio ou ausente
    with pytest.raises(ValueError, match="Team cannot be empty"):
        audit_sprint_state({"prioritized_tasks": tasks, "team": []})
    with pytest.raises(ValueError, match="Team cannot be empty"):
        validation_node({"prioritized_tasks": tasks, "team": None})

    # Tarefas vazias ou ausentes
    with pytest.raises(ValueError, match="Tasks .* cannot be empty"):
        audit_sprint_state({"team": team, "prioritized_tasks": [], "backlog": []})
    with pytest.raises(ValueError, match="Tasks .* cannot be empty"):
        validation_node({"team": team, "prioritized_tasks": None, "backlog": None})


def test_strict_mode_raises_value_error_on_violation():
    """Levanta ValueError consolidado em validation_node quando strict=True e há violações."""
    tasks, team = load_scenario("scenario_a")
    state_invalid: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": [],  # Violação de completude
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    with pytest.raises(ValueError) as excinfo:
        validation_node(state_invalid, strict=True)

    assert "Validation failed with" in str(excinfo.value)
    assert "allocations list is empty" in str(excinfo.value)


def test_anti_idor_developer_and_task():
    """Registra violação Anti-IDOR se allocation referenciar dev inexistente ou task desconhecida."""
    tasks, team = load_scenario("scenario_a")
    allocations = [
        Allocation(
            task_id=tasks[0].id,
            developer_id="dev_Hacker",
            allocated_points=tasks[0].story_points,
            reason="hacked dev",
        ),
        Allocation(
            task_id="TSK-999-FAKE",
            developer_id=team[0].id,
            allocated_points=3,
            reason="hacked task",
        ),
    ]

    state: SprintState = {
        "backlog": tasks,
        "team": team,
        "prioritized_tasks": tasks,
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert any("anti-idor" in v.lower() and "dev_hacker" in v.lower() for v in report.violations)
    assert any("anti-idor" in v.lower() and "tsk-999-fake" in v.lower() for v in report.violations)


def test_anti_idor_cross_stage_phantom_task():
    """Registra violação Anti-IDOR entre estágios se prioritized_tasks injetar tarefa fantasma fora do backlog."""
    tasks, team = load_scenario("scenario_a")
    phantom_task = Task(
        id="TSK-PHANTOM",
        title="Phantom Injected",
        description="Phantom description",
        story_points=3,
        skill_required="frontend",
        priority=1,
    )
    tampered_tasks = list(tasks) + [phantom_task]
    allocations = deterministic_allocation(tasks, team)

    state: SprintState = {
        "backlog": tasks,  # Backlog canônico
        "team": team,
        "prioritized_tasks": tampered_tasks,  # Injetou TSK-PHANTOM
        "allocations": allocations,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    report = audit_sprint_state(state)
    assert report.is_valid is False
    assert any(
        "anti-idor" in v.lower() and "tsk-phantom" in v.lower() and "backlog" in v.lower()
        for v in report.violations
    )


def test_concurrency_thread_safety():
    """Garante isolamento de thread e ausência de race conditions em 10 execuções simultâneas."""
    tasks_a, team_a = load_scenario("scenario_a")
    ordered_ids = deterministic_topological_sort(tasks_a)
    task_map = {t.id: t for t in tasks_a}
    prioritized_a = [task_map[tid] for tid in ordered_ids]
    allocs_a = deterministic_allocation(prioritized_a, team_a)

    valid_state: SprintState = {
        "backlog": tasks_a,
        "team": team_a,
        "prioritized_tasks": prioritized_a,
        "allocations": allocs_a,
        "validation_errors": [],
        "sprint_plan": None,
        "messages": [],
    }

    invalid_state: SprintState = {
        "backlog": tasks_a,
        "team": team_a,
        "prioritized_tasks": prioritized_a,
        "allocations": [],  # inválido
        "validation_errors": ["residual_error_do_not_leak"],
        "sprint_plan": None,
        "messages": [],
    }

    def execute_validation(worker_id: int):
        if worker_id % 2 == 0:
            res = validation_node(valid_state)
            return ("valid", res)
        else:
            res = validation_node(invalid_state)
            return ("invalid", res)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(execute_validation, i) for i in range(10)]
        results = [f.result() for f in futures]

    for outcome_type, res in results:
        if outcome_type == "valid":
            assert res["validation_errors"] == []
            assert "APPROVED" in str(res["messages"][0].content)
        else:
            assert len(res["validation_errors"]) > 0
            assert "REJECTED" in str(res["messages"][0].content)

    # Imutabilidade estrita das instâncias originais
    assert valid_state["validation_errors"] == []
    assert invalid_state["validation_errors"] == ["residual_error_do_not_leak"]


def test_validator_node_alias():
    """Garante que validator_node é alias idêntico de validation_node."""
    assert validator_node is validation_node


def test_validation_report_extra_forbid():
    """Garante que ValidationReport rejeita campos extras com Pydantic v2 extra='forbid'."""
    with pytest.raises(Exception):
        ValidationReport(
            is_valid=True,
            is_feasible=True,
            violations=[],
            allocated_by_dev={},
            capacities={},
            summary="All clear",
            injected_malicious_key="exploit",
        )
