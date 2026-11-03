"""Hybrid LangSmith Observability and BDI Deliberation Traceability Module (telemetry.py)."""

import os
import uuid
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from sprint_mas.state import Allocation, SprintPlan, SprintState


class DeliberationStep(BaseModel):
    """Represents a single agent deliberation step mapped to a BDI cognitive layer."""

    model_config = ConfigDict(extra="forbid")

    step_index: int = Field(..., ge=1, description="1-based chronological index of the deliberation step.")
    agent_node: str = Field(..., description="Identifier of the executed LangGraph node.")
    bdi_phase: str = Field(..., description="Mapped BDI cognitive phase (e.g., desires, intentions_draft).")
    headline: str = Field(..., description="Header line of the agent deliberation message.")
    content_preview: str = Field(..., description="Concise preview of the agent deliberation reasoning.")


class DeliberationTraceReport(BaseModel):
    """Canonical structured trace report for a multi-agent sprint planning run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="Unique execution trace identifier.")
    thread_id: str = Field(..., description="Session thread identifier.")
    scenario: str = Field(..., description="Executed scenario identifier.")
    langsmith_enabled: bool = Field(..., description="Whether remote LangSmith tracing was active.")
    langsmith_project: str = Field(..., description="Target LangSmith project name.")
    execution_time_ms: float = Field(..., ge=0.0, description="Monotonic execution time in milliseconds.")
    nodes_traversed: list[str] = Field(default_factory=list, description="Ordered list of visited graph nodes.")
    validation_attempts: int = Field(..., ge=0, description="Number of deterministic validator audit passes.")
    replan_triggered: bool = Field(..., description="Whether the corrective replan node was activated.")
    is_approved: bool = Field(..., description="Whether the final sprint plan was approved by governance.")
    total_tasks_allocated: int = Field(..., ge=0, description="Total number of tasks allocated in the final state.")
    total_points_allocated: int = Field(..., ge=0, description="Total story points allocated in the final state.")
    deliberation_steps: list[DeliberationStep] = Field(
        default_factory=list,
        description="Chronological list of BDI deliberation steps.",
    )
    graph_mermaid: str = Field(..., description="Mermaid diagram of the compiled LangGraph topology.")


def mask_secret(secret: Optional[str]) -> str:
    """Masks sensitive API keys so they are never exposed in logs, CLI output, or JSON reports.

    Args:
        secret: Raw secret string or None.

    Returns:
        str: Empty string if None/blank, '***' if <= 8 chars, or 'xxxx...yyyy' otherwise.
    """
    if secret is None:
        return ""
    cleaned = secret.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "***"
    return f"{cleaned[:4]}...{cleaned[-4:]}"


def configure_langsmith_tracing(
    enabled: Optional[bool] = None,
    project_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Configures and synchronizes LangSmith / LangChain v2 tracing environment variables safely.

    If tracing is requested (via argument or environment variable) but no valid API key is present,
    it gracefully disables remote tracing and falls back to local telemetry to prevent HTTP 401 errors.

    Args:
        enabled: Optional explicit toggle for LangSmith tracing.
        project_name: Optional explicit LangSmith project name.
        api_key: Optional explicit LangSmith API key.

    Returns:
        dict[str, Any]: Configuration summary with masked secret and status reason.
    """
    if enabled is not None:
        tracing_requested = bool(enabled)
    else:
        env_ls = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
        env_lc = os.environ.get("LANGCHAIN_TRACING_V2", "").strip().lower()
        tracing_requested = env_ls in {"true", "1", "yes"} or env_lc in {"true", "1", "yes"}

    raw_project = (
        project_name
        or os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or "sprint-planning-mas"
    )
    resolved_project = raw_project.strip() or "sprint-planning-mas"

    if api_key is not None:
        resolved_key = api_key.strip()
    else:
        resolved_key = (
            os.environ.get("LANGSMITH_API_KEY")
            or os.environ.get("LANGCHAIN_API_KEY")
            or ""
        ).strip()

    os.environ["LANGSMITH_PROJECT"] = resolved_project
    os.environ["LANGCHAIN_PROJECT"] = resolved_project

    if not tracing_requested:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return {
            "tracing_enabled": False,
            "project_name": resolved_project,
            "api_key_masked": mask_secret(resolved_key),
            "reason": "LangSmith tracing disabled by configuration.",
        }

    if not resolved_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return {
            "tracing_enabled": False,
            "project_name": resolved_project,
            "api_key_masked": "",
            "reason": "Missing LANGSMITH_API_KEY; falling back to local telemetry.",
        }

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_API_KEY"] = resolved_key

    return {
        "tracing_enabled": True,
        "project_name": resolved_project,
        "api_key_masked": mask_secret(resolved_key),
        "reason": "LangSmith cloud tracing enabled.",
    }


def build_langsmith_run_config(
    thread_id: str = "default",
    scenario_name: str = "custom",
    sprint_goal: str = "",
    max_retries: int = 2,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Builds a LangGraph RunnableConfig enriched with BDI and experimental metadata.

    Args:
        thread_id: Session thread identifier for checkpoint isolation.
        scenario_name: Name of the experimental scenario (e.g., 'scenario_a', 'scenario_b').
        sprint_goal: Executive sprint objective.
        max_retries: Circuit breaker retry ceiling.
        sprint_days: Sprint duration in business days.
        points_per_day: Nominal story points per full-time day.
        tags: Optional list of custom LangSmith tags.
        metadata: Optional dictionary of custom LangSmith metadata.

    Returns:
        dict[str, Any]: Compatible RunnableConfig dictionary for graph.invoke().
    """
    default_tags = [
        "sprint-mas",
        "bdi-architecture",
        f"scenario:{scenario_name}",
        "reic-2026",
        "wesaac-2025",
    ]
    merged_tags = list(dict.fromkeys(default_tags + (tags or [])))

    merged_metadata: dict[str, Any] = {
        "scenario": scenario_name,
        "thread_id": thread_id,
        "sprint_goal": sprint_goal,
        "max_retries": max_retries,
        "sprint_days": sprint_days,
        "points_per_day": points_per_day,
        "bdi_layers": [
            "beliefs:SprintState",
            "desires:BART_YAML",
            "intentions:SprintPlan",
        ],
        **(metadata or {}),
    }

    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": max(50, (max_retries + 2) * 5),
        "run_name": f"sprint-mas:{scenario_name}",
        "tags": merged_tags,
        "metadata": merged_metadata,
    }


def get_graph_mermaid(graph: Optional[Any] = None) -> str:
    """Extracts the Mermaid diagram string representing the compiled LangGraph topology.

    Args:
        graph: Optional compiled StateGraph instance. If None, builds the default sprint graph.

    Returns:
        str: Mermaid flowchart definition of the multi-agent state machine.
    """
    if graph is None:
        from sprint_mas.graph import build_sprint_graph

        graph = build_sprint_graph()

    return str(graph.get_graph().draw_mermaid())


_HEADER_TO_NODE_BDI: tuple[tuple[str, str, str], ...] = (
    ("### Prioritizer Agent Deliberation", "prioritizer", "desires"),
    ("### Allocator Agent Deliberation", "allocator", "intentions_draft"),
    ("### Validator Agent Deliberation", "validator", "governance_audit"),
    ("### Replan Agent Deliberation", "replan", "corrective_replan"),
    ("### Supervisor Agent Deliberation", "supervisor", "intentions_consolidated"),
)


def extract_deliberation_trace(
    state: Union[SprintState, dict[str, Any]],
    scenario: str = "custom",
    thread_id: str = "default",
    execution_time_ms: float = 0.0,
    langsmith_enabled: bool = False,
    langsmith_project: str = "sprint-planning-mas",
    graph_mermaid: str = "",
) -> DeliberationTraceReport:
    """Reconstructs the complete step-by-step BDI deliberation trace from a SprintState without mutating it.

    Args:
        state: Final or intermediate SprintState dictionary.
        scenario: Executed scenario name.
        thread_id: Session identifier.
        execution_time_ms: Measured execution duration in milliseconds.
        langsmith_enabled: Whether remote LangSmith tracing was active.
        langsmith_project: Configured LangSmith project name.
        graph_mermaid: Optional pre-rendered Mermaid topology string.

    Returns:
        DeliberationTraceReport: Immutable Pydantic v2 telemetry report.
    """
    messages = list(state.get("messages") or [])
    steps: list[DeliberationStep] = []
    nodes_traversed: list[str] = []

    for msg in messages:
        content = str(getattr(msg, "content", msg if isinstance(msg, str) else "")).strip()
        if not content:
            continue

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        headline = lines[0] if lines else "Agent Deliberation"
        body_lines = lines[1:] if len(lines) > 1 else lines
        preview = " | ".join(body_lines)[:240]

        matched_node = "unknown"
        matched_phase = "unknown"
        for prefix, node_name, bdi_phase in _HEADER_TO_NODE_BDI:
            if prefix in headline or content.startswith(prefix):
                matched_node = node_name
                matched_phase = bdi_phase
                break

        step_idx = len(steps) + 1
        nodes_traversed.append(matched_node)
        steps.append(
            DeliberationStep(
                step_index=step_idx,
                agent_node=matched_node,
                bdi_phase=matched_phase,
                headline=headline,
                content_preview=preview,
            )
        )

    validation_attempts = sum(1 for node in nodes_traversed if node == "validator")
    replan_triggered = "replan" in nodes_traversed

    sprint_plan_raw = state.get("sprint_plan")
    validation_errors = list(state.get("validation_errors") or [])
    is_approved = sprint_plan_raw is not None and len(validation_errors) == 0

    if isinstance(sprint_plan_raw, SprintPlan):
        total_tasks_allocated = len(sprint_plan_raw.allocations)
        total_points_allocated = sprint_plan_raw.total_points
    elif isinstance(sprint_plan_raw, dict):
        allocs = sprint_plan_raw.get("allocations", [])
        total_tasks_allocated = len(allocs)
        total_points_allocated = int(sprint_plan_raw.get("total_points", 0))
    else:
        allocs_raw = list(state.get("allocations") or [])
        total_tasks_allocated = len(allocs_raw)
        total_points_allocated = sum(
            a.allocated_points if isinstance(a, Allocation) else int(a.get("allocated_points", 0))
            for a in allocs_raw
        )

    resolved_mermaid = graph_mermaid if graph_mermaid else get_graph_mermaid()

    return DeliberationTraceReport(
        run_id=f"run-{uuid.uuid4().hex[:12]}",
        thread_id=thread_id,
        scenario=scenario,
        langsmith_enabled=langsmith_enabled,
        langsmith_project=langsmith_project,
        execution_time_ms=round(max(0.0, float(execution_time_ms)), 3),
        nodes_traversed=nodes_traversed,
        validation_attempts=validation_attempts,
        replan_triggered=replan_triggered,
        is_approved=is_approved,
        total_tasks_allocated=total_tasks_allocated,
        total_points_allocated=total_points_allocated,
        deliberation_steps=steps,
        graph_mermaid=resolved_mermaid,
    )


def validate_safe_output_path(
    output_path: Union[str, Path],
    base_dir: Optional[Path] = None,
) -> Path:
    """Validates an output file path against Path Traversal and unauthorized file extensions.

    Args:
        output_path: Requested relative or absolute file path.
        base_dir: Base project directory (defaults to repository root).

    Returns:
        Path: Resolved, verified Path inside the repository root with a .json or .md extension.

    Raises:
        ValueError: If the path is empty, escapes the repository root, or has a disallowed extension.
    """
    if output_path is None or not str(output_path).strip():
        raise ValueError("Security violation: output path cannot be empty.")

    resolved_base = (
        base_dir.resolve()
        if base_dir is not None
        else Path(__file__).resolve().parent.parent
    )

    raw_str = str(output_path).strip()
    candidate = Path(raw_str)
    if candidate.is_absolute():
        target = candidate.resolve()
    else:
        target = (resolved_base / candidate).resolve()

    if not target.is_relative_to(resolved_base):
        raise ValueError("Security violation: output path must be inside the project directory.")

    if target.suffix.lower() not in {".json", ".md"}:
        raise ValueError("Security violation: output file extension must be .json or .md.")

    return target
