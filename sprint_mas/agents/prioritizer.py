"""Agente de Priorização (Product Owner Node) do Sprint Planning MAS."""

import heapq
import json
import re
from typing import Any, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from sprint_mas.llm_factory import get_llm
from sprint_mas.prompts import get_agent_prompt_template
from sprint_mas.state import SprintState, Task
from sprint_mas.tools import get_topological_order


class PrioritizationOutput(BaseModel):
    """Esquema de saída estruturada do Agente de Priorização."""

    prioritized_task_ids: list[str] = Field(
        ..., description="Lista ordenada de IDs de tarefas."
    )
    prioritization_reasoning: str = Field(
        ..., description="Justificativa da ordenação."
    )


def deterministic_topological_sort(tasks: list[Union[Task, dict]]) -> list[str]:
    """Ordenação topológica (Kahn) com desempate determinístico por valor de negócio.

    Garante causalidade técnica e maximização de valor de negócio.
    Para nós prontos (in_degree == 0), utiliza uma min-heap ordenada por:
        (priority, -story_points, id)
    onde:
        - priority: 1 (mais alta prioridade) precede 2, 3, 4, 5.
        - -story_points: maior esforço primeiro em caso de empate de prioridade.
        - id: desempate alfanumérico determinístico.

    Args:
        tasks: Lista de tarefas a serem ordenadas (instâncias de Task ou dicts).

    Returns:
        list[str]: Lista ordenada de IDs de tarefas.

    Raises:
        ValueError: Caso exista dependência órfã ou ciclo no grafo.
    """
    in_degree: dict[str, int] = {}
    dependents: dict[str, list[str]] = {}
    all_ids: set[str] = set()
    task_metadata: dict[str, tuple[int, int]] = {}  # tid -> (priority, story_points)

    task_deps_map: dict[str, list[str]] = {}
    for task in tasks:
        if isinstance(task, Task):
            tid = task.id
            priority = task.priority
            story_points = task.story_points
            deps = list(task.dependencies)
        elif isinstance(task, dict):
            tid = str(task.get("id"))
            priority = int(task.get("priority", 3))
            story_points = int(task.get("story_points", 1))
            deps = list(task.get("dependencies", []))
        else:
            continue

        all_ids.add(tid)
        task_metadata[tid] = (priority, story_points)
        task_deps_map[tid] = deps
        in_degree[tid] = len(deps)
        dependents[tid] = []

    # Validação de dependências órfãs
    for tid, deps in task_deps_map.items():
        for dep in deps:
            if dep not in all_ids:
                raise ValueError(
                    f"Dependência órfã detectada: tarefa '{tid}' depende de '{dep}', "
                    "que não existe no conjunto de tarefas fornecido."
                )

    # Construção de arestas predecessor -> dependentes
    for tid, deps in task_deps_map.items():
        for dep in deps:
            if dep not in dependents:
                dependents[dep] = []
            dependents[dep].append(tid)

    # Min-heap com nós de in_degree == 0
    # Chave na heap: (priority, -story_points, tid)
    heap: list[tuple[int, int, str]] = []
    for tid in all_ids:
        if in_degree[tid] == 0:
            prio, sp = task_metadata[tid]
            heapq.heappush(heap, (prio, -sp, tid))

    ordered_ids: list[str] = []
    while heap:
        _, _, current_id = heapq.heappop(heap)
        ordered_ids.append(current_id)

        for dep_tid in dependents.get(current_id, []):
            in_degree[dep_tid] -= 1
            if in_degree[dep_tid] == 0:
                prio, sp = task_metadata[dep_tid]
                heapq.heappush(heap, (prio, -sp, dep_tid))

    if len(ordered_ids) < len(all_ids):
        unresolved = set(all_ids) - set(ordered_ids)
        raise ValueError(
            f"Ciclo de dependência circular detectado. "
            f"Não foi possível ordenar as tarefas: {unresolved}."
        )

    return ordered_ids


def validate_prioritization_order(
    tasks: list[Union[Task, dict]], candidate_ids: list[str]
) -> None:
    """Valida a conformidade estrita da lista de tarefas priorizadas candidatas.

    Regras de validação:
    a) Anti-IDOR: Nenhum ID desconhecido pode constar em candidate_ids.
    b) Conjunto de tarefas: Todas as tarefas do backlog devem constar exatamente uma vez (sem omissões nem duplicatas).
    c) Causalidade do DAG: Para toda tarefa V que depende de U, U deve preceder V na ordenação (`pos[U] < pos[V]`).

    Args:
        tasks: Lista original de tarefas do backlog.
        candidate_ids: Lista proposta de IDs ordenada.

    Raises:
        ValueError: Se alguma regra for violada.
    """
    task_map: dict[str, list[str]] = {}
    for task in tasks:
        if isinstance(task, Task):
            task_map[task.id] = list(task.dependencies)
        elif isinstance(task, dict):
            task_map[str(task.get("id"))] = list(task.get("dependencies", []))

    backlog_ids = set(task_map.keys())
    candidate_set = set(candidate_ids)

    # a) Anti-IDOR: IDs desconhecidos
    unknown_ids = candidate_set - backlog_ids
    if unknown_ids:
        raise ValueError(
            f"Violação Anti-IDOR: IDs de tarefas desconhecidos encontrados na priorização: {sorted(unknown_ids)}."
        )

    # b) Duplicatas
    if len(candidate_ids) != len(candidate_set):
        duplicates = [tid for tid in candidate_ids if candidate_ids.count(tid) > 1]
        raise ValueError(
            f"Tarefas duplicadas encontradas na priorização: {sorted(set(duplicates))}."
        )

    # b) Tarefas faltantes
    missing_ids = backlog_ids - candidate_set
    if missing_ids:
        raise ValueError(
            f"Tarefas faltantes na priorização: {sorted(missing_ids)}."
        )

    # c) Causalidade do DAG
    pos_map: dict[str, int] = {tid: idx for idx, tid in enumerate(candidate_ids)}
    for tid, deps in task_map.items():
        v_pos = pos_map[tid]
        for dep in deps:
            if dep in pos_map:
                u_pos = pos_map[dep]
                if u_pos >= v_pos:
                    raise ValueError(
                        f"Inversão causal de dependência detectada: tarefa '{tid}' (posição {v_pos}) "
                        f"aparece antes ou junta de sua dependência '{dep}' (posição {u_pos})."
                    )


def _clean_json_markdown(content: str) -> str:
    """Extrai conteúdo JSON limpo caso esteja encapsulado em markdown code fences."""
    content_str = content.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content_str, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return content_str


def prioritization_node(
    state: SprintState,
    llm: Optional[BaseChatModel] = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Nó do LangGraph para o Agente de Priorização (Product Owner Node).

    Orquestra a análise cognitiva e determinística do backlog:
    1. Rejeita backlog vazio ou ausente.
    2. Invoca a ferramenta analítica `get_topological_order` para fornecer o contexto causal.
    3. Serializa o backlog e monta o ChatPromptTemplate compilado do YAML.
    4. Invoca o modelo LLM configurado (ou via fábrica `get_llm(temperature=0.0)`).
    5. Parseia a saída em `PrioritizationOutput` e audita com `validate_prioritization_order`.
    6. Se inválido: se strict=True levanta ValueError; se strict=False aplica
       fallback seguro via `deterministic_topological_sort` garantindo 0% de erro causal.
    7. Retorna `{"prioritized_tasks": prioritized_tasks, "messages": [AIMessage(...)]}`.

    Args:
        state: Estado compartilhado da sprint (`SprintState`).
        llm: Modelo LangChain opcional para injeção de dependência / mocks.
        strict: Se True, falhas de validação disparam ValueError. Se False, ativa fallback resiliente.

    Returns:
        dict[str, Any]: Atualização para o SprintState contendo prioritized_tasks e messages.

    Raises:
        ValueError: Se backlog for vazio ou se validação falhar com strict=True.
    """
    backlog_raw = state.get("backlog")
    if not backlog_raw:
        raise ValueError("O backlog de tarefas está vazio ou ausente no SprintState.")

    # Converte para instâncias Task caso necessário
    backlog: list[Task] = []
    for item in backlog_raw:
        if isinstance(item, Task):
            backlog.append(item)
        elif isinstance(item, dict):
            backlog.append(Task(**item))
        else:
            raise ValueError(f"Item de backlog inválido no estado: {type(item)}")

    # 1. Ordem topológica pré-computada pelas ferramentas determinísticas
    topological_order_list = get_topological_order.invoke({"tasks": backlog})
    topological_order_json = json.dumps(topological_order_list, ensure_ascii=False)

    # 2. Serialização limpa do backlog
    clean_backlog_list = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "story_points": t.story_points,
            "skill_required": t.skill_required,
            "priority": t.priority,
            "dependencies": t.dependencies,
        }
        for t in backlog
    ]
    backlog_json = json.dumps(clean_backlog_list, ensure_ascii=False, indent=2)

    # 3. Compilação do prompt a partir de configs/prompts/prioritization.yaml
    prompt_template = get_agent_prompt_template("prioritization")

    # 4. Resolução de LLM
    active_llm = llm or get_llm(temperature=0.0)

    # 5. Formatação das mensagens e invocação do LLM
    formatted_messages = prompt_template.format_messages(
        backlog_json=backlog_json,
        topological_order_json=topological_order_json,
    )

    prioritized_ids: list[str] = []
    reasoning: str = ""

    try:
        response = active_llm.invoke(formatted_messages)
        response_text = _clean_json_markdown(str(response.content))
        data = json.loads(response_text)
        parsed_output = PrioritizationOutput(**data)
        candidate_ids = parsed_output.prioritized_task_ids
        reasoning = parsed_output.prioritization_reasoning

        # Validação estrita de conformidade (anti-IDOR, completude, causalidade do DAG)
        validate_prioritization_order(backlog, candidate_ids)
        prioritized_ids = candidate_ids
    except Exception as exc:
        if strict:
            raise ValueError(
                f"Falha na validação da priorização do LLM (strict=True): {exc}"
            ) from exc

        # Fallback seguro determinístico garantindo 0% de erro causal
        prioritized_ids = deterministic_topological_sort(backlog)
        reasoning = (
            f"[Fallback Determinístico Ativado]: A saída do LLM falhou na validação "
            f"({exc}). Aplicada ordenação topológica com desempate por min-heap "
            "(prioridade de negócio e story points) para assegurar 0% de erro causal."
        )

    # 6. Reconstrução da lista de objetos Task na ordem priorizada
    task_by_id = {t.id: t for t in backlog}
    prioritized_tasks = [task_by_id[tid] for tid in prioritized_ids]

    ai_message = AIMessage(
        content=(
            f"### Prioritizer Agent Deliberation\n\n"
            f"{reasoning}\n\n"
            f"**Total de tarefas priorizadas**: {len(prioritized_tasks)}"
        )
    )

    return {
        "prioritized_tasks": prioritized_tasks,
        "messages": [ai_message],
    }


# Alias oficial conforme especificação da Fase 4
prioritizer_node = prioritization_node
