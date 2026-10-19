"""Bateria de testes unitários para a camada de carregamento de cenários e validação de DAG."""

from pathlib import Path
import pytest

from sprint_mas.data_loader import (
    get_data_dir,
    list_available_scenarios,
    load_scenario,
    validate_dependencies_dag,
)
from sprint_mas.state import DeveloperProfile, Task


def test_get_data_dir():
    """Valida se o diretório de dados é localizado dinamicamente e existe."""
    data_dir = get_data_dir()
    assert isinstance(data_dir, Path)
    assert data_dir.is_dir()
    assert (data_dir / "processed").is_dir()


def test_list_scenarios():
    """Valida a listagem ordenada de todos os cenários disponíveis em data/processed."""
    scenarios = list_available_scenarios()
    assert isinstance(scenarios, list)
    assert "scenario_a" in scenarios
    assert "scenario_b" in scenarios
    assert "scenario_c" in scenarios
    assert scenarios == sorted(scenarios)


def test_load_scenario_a():
    """Valida o carregamento do Cenário A (Smoke Test: 10 tarefas e 3 desenvolvedores)."""
    tasks, team = load_scenario("scenario_a")
    assert len(tasks) == 10
    assert len(team) == 3

    # Valida formato e tipos
    assert all(isinstance(t, Task) for t in tasks)
    assert all(isinstance(d, DeveloperProfile) for d in team)

    # Valida que todos os devs possuem FTE = 1.0 no cenário A
    for dev in team:
        assert dev.fte == 1.0


def test_load_scenario_b_conformance():
    """Valida estrita conformidade do Cenário B com os papers WESAAC 2025 e REIC 2026.

    Critérios do paper:
    1. Exatamente 30 tarefas (TSK-101 a TSK-130).
    2. Exatamente 19 tarefas exigem competência 'backend' (63.3% do backlog).
    3. Exatamente 5 desenvolvedores com perfis e FTEs estritos:
       - dev_A: Frontend Developer, fte: 1.0
       - dev_B: Backend Specialist, fte: 0.7
       - dev_C: Fullstack Developer, fte: 1.0
       - dev_D: Backend Specialist, fte: 0.5 (gargalo crítico)
       - dev_E: Frontend Developer, fte: 1.0
    4. Encadeamentos de dependência especificados presentes e válidos.
    """
    tasks, team = load_scenario("scenario_b")

    # 1. Quantidade de tarefas
    assert len(tasks) == 30
    task_ids = [t.id for t in tasks]
    assert task_ids[0] == "TSK-101"
    assert task_ids[-1] == "TSK-130"

    # 2. Concentração de backend (exatamente 19 tarefas)
    backend_tasks = [t for t in tasks if t.skill_required.lower() == "backend"]
    assert len(backend_tasks) == 19
    backend_ratio = len(backend_tasks) / len(tasks)
    assert round(backend_ratio, 3) == 0.633

    # 3. Equipe canônica do paper
    assert len(team) == 5
    dev_map = {d.id: d for d in team}

    assert "dev_A" in dev_map
    assert dev_map["dev_A"].name == "Frontend Developer"
    assert dev_map["dev_A"].fte == 1.0
    assert "frontend" in dev_map["dev_A"].skills

    assert "dev_B" in dev_map
    assert dev_map["dev_B"].name == "Backend Specialist"
    assert dev_map["dev_B"].fte == 0.7
    assert "backend" in dev_map["dev_B"].skills

    assert "dev_C" in dev_map
    assert dev_map["dev_C"].name == "Fullstack Developer"
    assert dev_map["dev_C"].fte == 1.0
    assert "backend" in dev_map["dev_C"].skills
    assert "frontend" in dev_map["dev_C"].skills

    assert "dev_D" in dev_map
    assert dev_map["dev_D"].name == "Backend Specialist"
    assert dev_map["dev_D"].fte == 0.5  # Gargalo crítico!
    assert "backend" in dev_map["dev_D"].skills

    assert "dev_E" in dev_map
    assert dev_map["dev_E"].name == "Frontend Developer"
    assert dev_map["dev_E"].fte == 1.0
    assert "frontend" in dev_map["dev_E"].skills

    # 4. Cadeias de dependências
    task_dict = {t.id: t for t in tasks}
    assert "TSK-101" in task_dict["TSK-102"].dependencies
    assert "TSK-104" in task_dict["TSK-105"].dependencies
    assert "TSK-109" in task_dict["TSK-110"].dependencies
    assert "TSK-114" in task_dict["TSK-115"].dependencies
    assert "TSK-119" in task_dict["TSK-120"].dependencies


def test_load_scenario_b_flexible_naming():
    """Valida flexibilidade de nomenclatura ao carregar o cenário B ('b', 'scenario_b', 'scenario_b.json')."""
    tasks_1, team_1 = load_scenario("b")
    tasks_2, team_2 = load_scenario("scenario_b")
    tasks_3, team_3 = load_scenario("scenario_b.json")

    assert len(tasks_1) == len(tasks_2) == len(tasks_3) == 30
    assert len(team_1) == len(team_2) == len(team_3) == 5


def test_load_scenario_c():
    """Valida o Cenário C (Estresse & Escalabilidade: 100 tarefas e 10 desenvolvedores)."""
    tasks, team = load_scenario("scenario_c")
    assert len(tasks) == 100
    assert len(team) == 10
    assert tasks[0].id == "TSK-201"
    assert tasks[-1].id == "TSK-300"


def test_load_scenario_not_found():
    """Garante que FileNotFoundError é lançado para cenários inexistentes."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_scenario("scenario_inexistente_xyz")
    assert "Cenário não encontrado" in str(exc_info.value)


def test_duplicate_task_id():
    """Garante que IDs de tarefas duplicados disparam ValueError."""
    tasks = [
        Task(id="TSK-001", title="Tarefa 1", description="Desc 1", story_points=3, skill_required="backend", priority=1),
        Task(id="TSK-001", title="Tarefa 1 Duplicada", description="Desc 2", story_points=2, skill_required="backend", priority=2),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_dependencies_dag(tasks)
    assert "ID de tarefa duplicado detectado" in str(exc_info.value)


def test_orphan_dependency():
    """Garante que dependência apontando para tarefa inexistente dispara ValueError."""
    tasks = [
        Task(id="TSK-001", title="Tarefa 1", description="Desc 1", story_points=3, skill_required="backend", priority=1, dependencies=[]),
        Task(id="TSK-002", title="Tarefa 2", description="Desc 2", story_points=5, skill_required="backend", priority=2, dependencies=["TSK-INEXISTENTE"]),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_dependencies_dag(tasks)
    assert "Dependência órfã detectada" in str(exc_info.value)
    assert "TSK-INEXISTENTE" in str(exc_info.value)


def test_self_dependency():
    """Garante que tarefa dependendo de si mesma dispara ValueError."""
    tasks = [
        Task(id="TSK-SELF", title="Auto dependente", description="Desc", story_points=3, skill_required="backend", priority=1, dependencies=["TSK-SELF"]),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_dependencies_dag(tasks)
    assert "Auto-dependência detectada" in str(exc_info.value)
    assert "TSK-SELF" in str(exc_info.value)


def test_circular_dependency_simple():
    """Garante que ciclo simples de 2 nós (A -> B -> A) dispara ValueError."""
    tasks = [
        Task(id="TSK-A", title="A", description="Desc", story_points=2, skill_required="backend", priority=1, dependencies=["TSK-B"]),
        Task(id="TSK-B", title="B", description="Desc", story_points=2, skill_required="backend", priority=1, dependencies=["TSK-A"]),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_dependencies_dag(tasks)
    assert "Ciclo de dependência circular detectado" in str(exc_info.value)


def test_circular_dependency_chain():
    """Garante que ciclo em cadeia de múltiplos nós (A -> B -> C -> A) dispara ValueError."""
    tasks = [
        Task(id="TSK-A", title="A", description="Desc", story_points=2, skill_required="backend", priority=1, dependencies=["TSK-B"]),
        Task(id="TSK-B", title="B", description="Desc", story_points=2, skill_required="backend", priority=1, dependencies=["TSK-C"]),
        Task(id="TSK-C", title="C", description="Desc", story_points=2, skill_required="backend", priority=1, dependencies=["TSK-A"]),
        Task(id="TSK-D", title="D Independente", description="Desc", story_points=1, skill_required="frontend", priority=3, dependencies=[]),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_dependencies_dag(tasks)
    assert "Ciclo de dependência circular detectado" in str(exc_info.value)
