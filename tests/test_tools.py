"""Bateria de testes unitários para a biblioteca de ferramentas determinísticas do MAS."""

from pydantic import ValidationError
import pytest

from sprint_mas.data_loader import load_scenario
from sprint_mas.state import Allocation, DeveloperProfile, Task
from sprint_mas.tools import (
    calculate_team_capacity,
    check_allocation_feasibility,
    get_topological_order,
    match_skills,
)


def test_calculate_team_capacity_scenario_b():
    """Valida o cálculo exato de capacidade para a equipe do Cenário B (WESAAC 2025 / REIC 2026)."""
    _, team = load_scenario("scenario_b")

    result = calculate_team_capacity.invoke({
        "team_profiles": team,
        "sprint_days": 10,
        "points_per_day": 2.0,
    })

    capacities = result["capacities"]
    assert capacities["dev_A"] == 20.0  # 1.0 * 10 * 2
    assert capacities["dev_B"] == 14.0  # 0.7 * 10 * 2
    assert capacities["dev_C"] == 20.0  # 1.0 * 10 * 2
    assert capacities["dev_D"] == 10.0  # 0.5 * 10 * 2 (gargalo crítico)
    assert capacities["dev_E"] == 20.0  # 1.0 * 10 * 2

    assert result["total_team_capacity"] == 84.0
    assert result["sprint_days"] == 10
    assert result["points_per_day"] == 2.0


def test_calculate_team_capacity_with_dicts():
    """Valida que calculate_team_capacity aceita dicionários crus."""
    team_dicts = [
        {"id": "dev_1", "fte": 0.8},
        {"id": "dev_2", "fte": 0.5},
    ]
    result = calculate_team_capacity.invoke({
        "team_profiles": team_dicts,
        "sprint_days": 5,
        "points_per_day": 1.0,
    })

    assert result["capacities"]["dev_1"] == 4.0
    assert result["capacities"]["dev_2"] == 2.5
    assert result["total_team_capacity"] == 6.5


def test_calculate_team_capacity_invalid_type():
    """Garante que entrada com tipo inválido no invoke dispara erro de validação de schema."""
    with pytest.raises(ValidationError):
        calculate_team_capacity.invoke({"team_profiles": ["invalid_string_profile"]})


def test_calculate_team_capacity_func_type_error():
    """Garante que execução direta da função subjacente com tipo espúrio dispara TypeError."""
    with pytest.raises(TypeError) as exc_info:
        calculate_team_capacity.func(team_profiles=["invalid_string_profile"])
    assert "Tipo de perfil inválido" in str(exc_info.value)


def test_calculate_team_capacity_negative_days():
    """Garante que sprint_days <= 0 dispara ValueError explicativo."""
    with pytest.raises(ValueError) as exc_info:
        calculate_team_capacity.func(team_profiles=[{"id": "dev_1", "fte": 1.0}], sprint_days=-1)
    assert "Duração da sprint deve ser maior que zero" in str(exc_info.value)


def test_calculate_team_capacity_negative_velocity():
    """Garante que points_per_day <= 0 dispara ValueError explicativo."""
    with pytest.raises(ValueError) as exc_info:
        calculate_team_capacity.func(team_profiles=[{"id": "dev_1", "fte": 1.0}], points_per_day=0)
    assert "Taxa de pontos por dia deve ser maior que zero" in str(exc_info.value)


def test_calculate_team_capacity_negative_fte():
    """Garante que FTE negativo dispara ValueError defensivo."""
    with pytest.raises(ValueError) as exc_info:
        calculate_team_capacity.func(team_profiles=[{"id": "dev_bad", "fte": -0.5}])
    assert "não pode ser negativo" in str(exc_info.value)


def test_check_allocation_feasibility_success():
    """Valida viabilidade quando as alocações respeitam estritamente a capacidade máxima."""
    capacity = {
        "capacities": {
            "dev_A": 20.0,
            "dev_D": 10.0,
        }
    }
    tasks = [
        Task(id="T1", title="Task 1", description="D", story_points=5, skill_required="backend", priority=1),
        Task(id="T2", title="Task 2", description="D", story_points=5, skill_required="backend", priority=1),
        Task(id="T3", title="Task 3", description="D", story_points=8, skill_required="frontend", priority=1),
    ]
    allocations = [
        Allocation(task_id="T1", developer_id="dev_D", allocated_points=5, reason="API"),
        Allocation(task_id="T2", developer_id="dev_D", allocated_points=5, reason="API"),
        Allocation(task_id="T3", developer_id="dev_A", allocated_points=8, reason="UI"),
    ]

    result = check_allocation_feasibility.invoke({
        "allocations": allocations,
        "team_capacity": capacity,
        "tasks": tasks,
    })

    assert result["is_feasible"] is True
    assert len(result["violations"]) == 0
    assert result["allocated_by_dev"]["dev_D"] == 10
    assert result["allocated_by_dev"]["dev_A"] == 8


def test_check_allocation_feasibility_violation_dev_d():
    """Garante detecção de sobrecarga quando dev_D (teto 10 pts) recebe 15 pontos."""
    capacity = {
        "capacities": {
            "dev_D": 10.0,
        }
    }
    tasks = [
        {"id": "T1", "story_points": 8},
        {"id": "T2", "story_points": 7},
    ]
    allocations = [
        {"task_id": "T1", "developer_id": "dev_D", "allocated_points": 8},
        {"task_id": "T2", "developer_id": "dev_D", "allocated_points": 7},
    ]

    result = check_allocation_feasibility.invoke({
        "allocations": allocations,
        "team_capacity": capacity,
        "tasks": tasks,
    })

    assert result["is_feasible"] is False
    assert len(result["violations"]) == 1
    assert "dev_D" in result["violations"][0]
    assert "15 pts" in result["violations"][0]
    assert "10.0 pts" in result["violations"][0]


def test_check_allocation_feasibility_unknown_entities():
    """Valida proteção anti-IDOR detectando desenvolvedor ou tarefa inexistentes no contexto."""
    capacity = {
        "capacities": {
            "dev_A": 20.0,
        }
    }
    tasks = [
        {"id": "T1", "story_points": 5},
    ]
    allocations = [
        {"task_id": "T_INEXISTENTE", "developer_id": "dev_A", "allocated_points": 5},
        {"task_id": "T1", "developer_id": "dev_FANTASMA", "allocated_points": 5},
    ]

    result = check_allocation_feasibility.invoke({
        "allocations": allocations,
        "team_capacity": capacity,
        "tasks": tasks,
    })

    assert result["is_feasible"] is False
    assert len(result["violations"]) == 2
    assert any("T_INEXISTENTE" in v for v in result["violations"])
    assert any("dev_FANTASMA" in v for v in result["violations"])


def test_get_topological_order_causal_chains():
    """Valida que a ordenação topológica posiciona pré-requisitos antes das tarefas dependentes."""
    tasks = [
        Task(id="TSK-102", title="Consumer", description="D", story_points=5, skill_required="backend", priority=1, dependencies=["TSK-101"]),
        Task(id="TSK-101", title="Bus", description="D", story_points=5, skill_required="backend", priority=1, dependencies=[]),
        Task(id="TSK-105", title="Cache", description="D", story_points=3, skill_required="backend", priority=2, dependencies=["TSK-104"]),
        Task(id="TSK-104", title="Pricing", description="D", story_points=8, skill_required="backend", priority=2, dependencies=[]),
        Task(id="TSK-IND", title="Independent", description="D", story_points=2, skill_required="frontend", priority=3, dependencies=[]),
    ]

    order = get_topological_order.invoke({"tasks": tasks})

    assert len(order) == 5
    # TSK-101 deve vir antes de TSK-102
    assert order.index("TSK-101") < order.index("TSK-102")
    # TSK-104 deve vir antes de TSK-105
    assert order.index("TSK-104") < order.index("TSK-105")


def test_get_topological_order_orphan_dependency():
    """Garante que referência a dependência inexistente dispara ValueError explicativo."""
    tasks = [
        {"id": "T1", "dependencies": ["T_ORFA"]},
    ]
    with pytest.raises(ValueError) as exc_info:
        get_topological_order.invoke({"tasks": tasks})
    assert "Dependência órfã detectada" in str(exc_info.value)
    assert "T_ORFA" in str(exc_info.value)


def test_get_topological_order_cycle_detection():
    """Garante que tentativa de ordenação topológica com ciclo dispara ValueError."""
    tasks = [
        {"id": "T1", "dependencies": ["T2"]},
        {"id": "T2", "dependencies": ["T1"]},
    ]
    with pytest.raises(ValueError) as exc_info:
        get_topological_order.invoke({"tasks": tasks})
    assert "Ciclo de dependência circular detectado" in str(exc_info.value)


@pytest.mark.parametrize(
    "task_skill,dev_skills,expected",
    [
        ("backend", ["backend", "database"], True),
        ("Backend", ["backend"], True),
        ("frontend", ["ui", "frontend"], True),
        ("backend", ["fullstack", "ui"], True),      # Fullstack cobre backend
        ("frontend", ["fullstack"], True),          # Fullstack cobre frontend
        ("fullstack", ["fullstack"], True),
        ("devops", ["frontend", "ui"], False),      # Incompatível
        ("mobile", ["backend", "database"], False),  # Incompatível
    ],
)
def test_match_skills(task_skill, dev_skills, expected):
    """Valida regras de correspondência de competências técnicas diretas e de perfil fullstack."""
    assert match_skills.invoke({"task_skill": task_skill, "dev_skills": dev_skills}) == expected
