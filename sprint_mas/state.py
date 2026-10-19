"""Sprint Planning MAS State Schema and Domain Models."""

from typing import Annotated, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class Task(BaseModel):
    """Representa uma tarefa técnica no backlog da sprint."""

    id: str = Field(..., description="Identificador único da tarefa.")
    title: str = Field(..., description="Título descritivo da tarefa.")
    description: str = Field(..., description="Descrição detalhada dos requisitos da tarefa.")
    story_points: int = Field(..., gt=0, description="Estimativa de esforço em story points (deve ser > 0).")
    skill_required: str = Field(..., description="Habilidade técnica primária necessária para a tarefa.")
    priority: int = Field(..., ge=1, le=5, description="Nível de prioridade da tarefa, de 1 (mais baixa) a 5 (mais alta).")
    dependencies: list[str] = Field(default_factory=list, description="Lista de IDs de tarefas das quais esta depende.")


class DeveloperProfile(BaseModel):
    """Representa o perfil de um desenvolvedor do time de engenharia."""

    id: str = Field(..., description="Identificador único do desenvolvedor.")
    name: str = Field(..., description="Nome do desenvolvedor.")
    skills: list[str] = Field(default_factory=list, description="Conjunto de habilidades e tecnologias dominadas.")
    fte: float = Field(..., ge=0.0, le=1.0, description="Full-Time Equivalent / capacidade de dedicação (entre 0.0 e 1.0).")


class Allocation(BaseModel):
    """Representa a alocação de uma tarefa específica a um desenvolvedor."""

    task_id: str = Field(..., description="ID da tarefa alocada.")
    developer_id: str = Field(..., description="ID do desenvolvedor responsável.")
    reason: str = Field(..., description="Justificativa técnica da decisão de alocação.")
    allocated_points: int = Field(..., description="Story points atribuídos nesta alocação.")


class SprintPlan(BaseModel):
    """Representa o plano consolidado final da sprint."""

    sprint_name: str = Field(..., description="Nome ou identificador da sprint.")
    sprint_goal: str = Field(..., description="Objetivo principal a ser alcançado na sprint.")
    tasks: list[Task] = Field(default_factory=list, description="Tarefas selecionadas e priorizadas para a sprint.")
    allocations: list[Allocation] = Field(default_factory=list, description="Mapeamento completo de alocações.")
    total_points: int = Field(..., description="Total de story points planejados para a sprint.")
    summary: str = Field(..., description="Sumário executivo do planejamento e capacidade.")


class SprintState(TypedDict):
    """Estado compartilhado (Blackboard) do LangGraph para o fluxo multiagente de Sprint Planning."""

    backlog: list[Task]
    team: list[DeveloperProfile]
    prioritized_tasks: list[Task]
    allocations: list[Allocation]
    validation_errors: list[str]
    sprint_plan: Optional[SprintPlan]
    messages: Annotated[list[BaseMessage], add_messages]
