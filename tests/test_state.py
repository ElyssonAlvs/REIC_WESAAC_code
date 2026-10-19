"""Testes unitários para os modelos de domínio e SprintState."""

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from sprint_mas.state import (
    Allocation,
    DeveloperProfile,
    SprintPlan,
    SprintState,
    Task,
)


def test_task_creation_valid():
    """Valida a instanciação de uma Task com dados corretos."""
    task = Task(
        id="TASK-1",
        title="Implementar autenticação JWT",
        description="Criar middleware e endpoints de login",
        story_points=5,
        skill_required="Backend",
        priority=4,
        dependencies=["TASK-0"],
    )
    assert task.id == "TASK-1"
    assert task.title == "Implementar autenticação JWT"
    assert task.story_points == 5
    assert task.skill_required == "Backend"
    assert task.priority == 4
    assert task.dependencies == ["TASK-0"]


def test_task_default_dependencies():
    """Valida que dependencies assume lista vazia por padrão."""
    task = Task(
        id="TASK-2",
        title="Setup inicial",
        description="Configuração de repositório",
        story_points=1,
        skill_required="DevOps",
        priority=1,
    )
    assert task.dependencies == []


@pytest.mark.parametrize("invalid_points", [0, -1, -5])
def test_task_invalid_story_points(invalid_points):
    """Garante que story_points <= 0 lança ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Task(
            id="TASK-ERR",
            title="Tarefa com pontos inválidos",
            description="Descrição",
            story_points=invalid_points,
            skill_required="Backend",
            priority=3,
        )
    assert "story_points" in str(exc_info.value)


@pytest.mark.parametrize("invalid_priority", [0, -1, 6, 10])
def test_task_invalid_priority_range(invalid_priority):
    """Garante que prioridades fora do intervalo [1, 5] lançam ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Task(
            id="TASK-ERR-PRIO",
            title="Prioridade inválida",
            description="Descrição",
            story_points=3,
            skill_required="Frontend",
            priority=invalid_priority,
        )
    assert "priority" in str(exc_info.value)


def test_developer_profile_valid():
    """Valida a instanciação de um DeveloperProfile válido."""
    dev = DeveloperProfile(
        id="DEV-1",
        name="Alice Silva",
        skills=["Python", "FastAPI", "Docker"],
        fte=0.8,
    )
    assert dev.id == "DEV-1"
    assert dev.name == "Alice Silva"
    assert len(dev.skills) == 3
    assert dev.fte == 0.8


def test_developer_profile_default_skills():
    """Valida que skills assume lista vazia por padrão."""
    dev = DeveloperProfile(
        id="DEV-2",
        name="Bob Santos",
        fte=1.0,
    )
    assert dev.skills == []


@pytest.mark.parametrize("invalid_fte", [-0.1, -1.0, 1.1, 2.0])
def test_developer_profile_invalid_fte(invalid_fte):
    """Garante que FTE fora do intervalo [0.0, 1.0] lança ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        DeveloperProfile(
            id="DEV-ERR",
            name="Charlie",
            skills=["QA"],
            fte=invalid_fte,
        )
    assert "fte" in str(exc_info.value)


def test_allocation_creation():
    """Valida a instanciação de uma Allocation válida."""
    alloc = Allocation(
        task_id="TASK-1",
        developer_id="DEV-1",
        reason="Alice domina FastAPI e arquitetura de autenticação",
        allocated_points=5,
    )
    assert alloc.task_id == "TASK-1"
    assert alloc.developer_id == "DEV-1"
    assert alloc.allocated_points == 5


def test_sprint_plan_creation():
    """Valida a instanciação de um SprintPlan estruturado."""
    task = Task(
        id="TASK-1",
        title="Setup",
        description="Setup da base",
        story_points=3,
        skill_required="DevOps",
        priority=3,
    )
    alloc = Allocation(
        task_id="TASK-1",
        developer_id="DEV-1",
        reason="Match técnico",
        allocated_points=3,
    )
    plan = SprintPlan(
        sprint_name="Sprint 1",
        sprint_goal="Estabelecer fundação do sistema",
        tasks=[task],
        allocations=[alloc],
        total_points=3,
        summary="Sprint com 1 tarefa de infraestrutura.",
    )
    assert plan.sprint_name == "Sprint 1"
    assert plan.total_points == 3
    assert len(plan.tasks) == 1
    assert len(plan.allocations) == 1


def test_sprint_state_structure():
    """Valida a conformidade e estruturação de um dicionário do tipo SprintState."""
    task = Task(
        id="T1",
        title="Task 1",
        description="Desc 1",
        story_points=2,
        skill_required="Python",
        priority=5,
    )
    dev = DeveloperProfile(
        id="D1",
        name="Dev 1",
        skills=["Python"],
        fte=1.0,
    )
    alloc = Allocation(
        task_id="T1",
        developer_id="D1",
        reason="Capacidade adequada",
        allocated_points=2,
    )
    plan = SprintPlan(
        sprint_name="Sprint 1",
        sprint_goal="Meta 1",
        tasks=[task],
        allocations=[alloc],
        total_points=2,
        summary="Resumo inicial",
    )
    msg = HumanMessage(content="Iniciar planejamento da sprint")

    state: SprintState = {
        "backlog": [task],
        "team": [dev],
        "prioritized_tasks": [task],
        "allocations": [alloc],
        "validation_errors": [],
        "sprint_plan": plan,
        "messages": [msg],
    }

    assert len(state["backlog"]) == 1
    assert len(state["team"]) == 1
    assert len(state["prioritized_tasks"]) == 1
    assert len(state["allocations"]) == 1
    assert state["validation_errors"] == []
    assert state["sprint_plan"] is not None
    assert len(state["messages"]) == 1
