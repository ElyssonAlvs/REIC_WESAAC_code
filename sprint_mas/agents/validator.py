"""Deterministic Validator Agent (Validation Node) for Sprint Planning MAS."""

from typing import Any, Union

from langchain_core.messages import AIMessage
from pydantic import BaseModel, ConfigDict, Field

from sprint_mas.agents.allocator import is_dev_qualified
from sprint_mas.state import Allocation, DeveloperProfile, SprintState, Task
from sprint_mas.tools import calculate_team_capacity


class ValidationReport(BaseModel):
    """Structured report produced by the deterministic sprint state audit."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool = Field(
        ...,
        description="True if all validation checks passed with zero violations, False otherwise.",
    )
    is_feasible: bool = Field(
        ...,
        description="True if the sprint plan is executable within capacity and structural constraints.",
    )
    violations: list[str] = Field(
        default_factory=list,
        description="List of detailed violation messages detected during the audit.",
    )
    allocated_by_dev: dict[str, int] = Field(
        default_factory=dict,
        description="Total story points allocated to each developer (recalculated via canonical Task points).",
    )
    capacities: dict[str, float] = Field(
        default_factory=dict,
        description="Calculated analytical story point capacity ceilings per developer.",
    )
    summary: str = Field(
        ...,
        description="Executive summary of the validation and feasibility results.",
    )


def _detect_cycles(tasks: list[Task]) -> list[str]:
    """Detects cycles in the task dependency graph using DFS with 3-color marking.

    0 = WHITE (unvisited), 1 = GRAY (currently in recursion stack), 2 = BLACK (visited).
    Returns a list of cycle descriptions (e.g. 'TSK-1 -> TSK-2 -> TSK-1').
    """
    task_map = {t.id: t for t in tasks}
    color: dict[str, int] = {t.id: 0 for t in tasks}
    path: list[str] = []
    cycles: list[str] = []

    def dfs(node_id: str) -> None:
        color[node_id] = 1
        path.append(node_id)

        task = task_map.get(node_id)
        if task:
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    if color[dep_id] == 1:
                        cycle_start = path.index(dep_id)
                        cycle = path[cycle_start:] + [dep_id]
                        cycles.append(" -> ".join(cycle))
                    elif color[dep_id] == 0:
                        dfs(dep_id)

        path.pop()
        color[node_id] = 2

    for t in tasks:
        if color[t.id] == 0:
            dfs(t.id)

    return cycles


def audit_sprint_state(
    state: Union[SprintState, dict[str, Any]],
    sprint_days: int = 10,
    points_per_day: float = 2.0,
) -> ValidationReport:
    """Performs an exhaustive 5-dimensional deterministic audit on the SprintState.

    Audited Dimensions:
    1. Anti-IDOR:
       - Cross-stage integrity: All tasks in prioritized_tasks must exist in the backlog (if provided).
       - Entity integrity: All allocations must reference existing developers in team and scheduled tasks.
    2. Completeness & Uniqueness:
       - Allocations cannot be empty if tasks are present.
       - Each scheduled task must be allocated exactly once (no duplicates, no omissions).
    3. Server Authority on Story Points:
       - Detects tampering if Allocation.allocated_points != Task.story_points.
       - Recomputes developer workloads strictly using canonical Task.story_points.
    4. Causal DAG Integrity & Precedence:
       - All task dependencies must precede the task in prioritized_tasks (pos[dep] < pos[task]).
       - Dependencies must be scheduled in this sprint (detects unscheduled parent dependencies).
       - Detects orphan dependencies (referencing non-existent tasks) and circular dependency cycles.
    5. Skill Matching & FTE Capacity Ceilings:
       - Developers must be qualified for the required task skill (via is_dev_qualified).
       - Workload per developer must not exceed FTE analytical capacity (via calculate_team_capacity),
         specifically dev_D <= 10.0 pts (0.5 FTE) and dev_B <= 14.0 pts (0.7 FTE).

    Args:
        state: Shared SprintState or dictionary containing team, tasks, and allocations.
        sprint_days: Sprint duration in business days (default: 10, must be > 0).
        points_per_day: Nominal story points rate per full-time day (default: 2.0, must be > 0).

    Returns:
        ValidationReport: Immutable Pydantic v2 model with violations and feasibility metrics.

    Raises:
        ValueError: If sprint_days <= 0, points_per_day <= 0, or if team/tasks are missing or empty.
    """
    # 0. Structural precondition guards
    if sprint_days <= 0:
        raise ValueError(f"sprint_days must be greater than 0, got {sprint_days}.")
    if points_per_day <= 0:
        raise ValueError(f"points_per_day must be greater than 0, got {points_per_day}.")

    team_raw = state.get("team")
    if not team_raw:
        raise ValueError("Team cannot be empty or missing in SprintState.")

    tasks_raw = state.get("prioritized_tasks") or state.get("backlog")
    if not tasks_raw:
        raise ValueError(
            "Tasks ('prioritized_tasks' or 'backlog') cannot be empty or missing in SprintState."
        )

    # Normalize team models
    team: list[DeveloperProfile] = []
    for d in team_raw:
        if isinstance(d, DeveloperProfile):
            team.append(d)
        elif isinstance(d, dict):
            team.append(DeveloperProfile(**d))
        else:
            raise TypeError(f"Invalid developer profile item: {type(d)}")

    # Normalize scheduled tasks
    tasks: list[Task] = []
    for t in tasks_raw:
        if isinstance(t, Task):
            tasks.append(t)
        elif isinstance(t, dict):
            tasks.append(Task(**t))
        else:
            raise TypeError(f"Invalid task item: {type(t)}")

    # Normalize optional backlog (for cross-stage anti-IDOR check)
    backlog_raw = state.get("backlog")
    backlog_ids: set[str] = set()
    if backlog_raw:
        for b in backlog_raw:
            if isinstance(b, Task):
                backlog_ids.add(b.id)
            elif isinstance(b, dict):
                backlog_ids.add(str(b.get("id")))

    # Normalize allocations
    allocations_raw = state.get("allocations", [])
    allocations: list[Allocation] = []
    if allocations_raw:
        for a in allocations_raw:
            if isinstance(a, Allocation):
                allocations.append(a)
            elif isinstance(a, dict):
                allocations.append(Allocation(**a))
            elif hasattr(a, "task_id") and hasattr(a, "developer_id"):
                allocations.append(
                    Allocation(
                        task_id=a.task_id,
                        developer_id=a.developer_id,
                        allocated_points=a.allocated_points,
                        reason=getattr(a, "reason", ""),
                    )
                )

    violations: list[str] = []

    team_ids = {d.id for d in team}
    team_map = {d.id: d for d in team}
    task_map = {t.id: t for t in tasks}
    task_ids = set(task_map.keys())

    # ---------------------------------------------------------
    # Dimension 1: Anti-IDOR (Cross-Stage and Entity Validation)
    # ---------------------------------------------------------
    # Check if prioritized_tasks introduced phantom tasks not in original backlog
    if backlog_ids:
        for t in tasks:
            if t.id not in backlog_ids:
                violations.append(
                    f"Anti-IDOR violation: task '{t.id}' in prioritized_tasks does not exist in original backlog."
                )

    # Check allocation entity references
    for alloc in allocations:
        if alloc.developer_id not in team_ids:
            violations.append(
                f"Anti-IDOR violation: developer '{alloc.developer_id}' in allocation does not exist in team."
            )
        if alloc.task_id not in task_ids:
            violations.append(
                f"Anti-IDOR violation: task '{alloc.task_id}' in allocation does not exist in scheduled tasks."
            )

    # ---------------------------------------------------------
    # Dimension 2: Completeness, Uniqueness & Server Authority
    # ---------------------------------------------------------
    allocated_task_ids: list[str] = []
    allocated_counts: dict[str, int] = {}
    for alloc in allocations:
        allocated_task_ids.append(alloc.task_id)
        allocated_counts[alloc.task_id] = allocated_counts.get(alloc.task_id, 0) + 1

    if not allocations:
        violations.append(
            "Allocation completeness violation: allocations list is empty; no tasks were allocated."
        )
    else:
        # Check duplicate allocations
        for tid, count in allocated_counts.items():
            if count > 1 and tid in task_map:
                violations.append(
                    f"Uniqueness violation: task '{tid}' is allocated multiple times ({count} allocations)."
                )

        # Check missing tasks from scheduled tasks
        missing_tasks = task_ids - set(allocated_task_ids)
        for tid in sorted(missing_tasks):
            violations.append(
                f"Completeness violation: task '{tid}' from prioritized_tasks is not allocated."
            )

    # Story points check & Server Authority workload calculation
    allocated_by_dev: dict[str, int] = {d.id: 0 for d in team}
    for alloc in allocations:
        if alloc.task_id in task_map:
            canonical_task = task_map[alloc.task_id]
            # Detect points tampering
            if alloc.allocated_points != canonical_task.story_points:
                violations.append(
                    f"Story points tampering violation: allocation for task '{alloc.task_id}' specifies "
                    f"{alloc.allocated_points} points, but canonical task requires {canonical_task.story_points} points."
                )
            # Server Authority: always use canonical story_points for workload calculation
            effective_points = canonical_task.story_points
        else:
            effective_points = alloc.allocated_points

        if alloc.developer_id in allocated_by_dev:
            allocated_by_dev[alloc.developer_id] += effective_points

    # ---------------------------------------------------------
    # Dimension 3: DAG Causal Integrity & Precedence
    # ---------------------------------------------------------
    pos_map: dict[str, int] = {t.id: idx for idx, t in enumerate(tasks)}

    for t in tasks:
        for dep_id in t.dependencies:
            # Orphan dependency: dep does not exist in backlog (if provided) nor in tasks
            if backlog_ids and dep_id not in backlog_ids and dep_id not in task_map:
                violations.append(
                    f"Topological DAG orphan dependency violation: task '{t.id}' has orphan dependency '{dep_id}' that does not exist in the backlog."
                )
            elif not backlog_ids and dep_id not in task_map:
                violations.append(
                    f"Topological DAG orphan dependency violation: task '{t.id}' has orphan dependency '{dep_id}' that does not exist in tasks."
                )
            elif dep_id not in task_map:
                # Exists in backlog, but was not scheduled in this sprint
                violations.append(
                    f"Unscheduled dependency violation: task '{t.id}' depends on parent task '{dep_id}', which is not scheduled in this sprint."
                )
            else:
                # Both dep and t are in tasks: verify causal precedence
                dep_pos = pos_map[dep_id]
                t_pos = pos_map[t.id]
                if dep_pos >= t_pos:
                    violations.append(
                        f"Causal DAG inversion violation: task '{t.id}' (position {t_pos}) appears before or at the same position as its dependency '{dep_id}' (position {dep_pos})."
                    )

    # Check for circular dependency cycles
    cycles = _detect_cycles(tasks)
    for c in cycles:
        violations.append(
            f"Topological DAG circular dependency violation: circular dependency cycle detected: {c}."
        )

    # Also check if any allocated task depends on an unscheduled parent in allocations
    alloc_task_set = set(allocated_task_ids)
    for alloc in allocations:
        if alloc.task_id in task_map:
            t = task_map[alloc.task_id]
            for dep_id in t.dependencies:
                if dep_id in task_map and dep_id not in alloc_task_set:
                    unscheduled_msg = (
                        f"Unscheduled dependency violation: allocated task '{t.id}' depends on parent task "
                        f"'{dep_id}', which is not allocated in this sprint."
                    )
                    if unscheduled_msg not in violations:
                        violations.append(unscheduled_msg)

    # ---------------------------------------------------------
    # Dimension 4: Skill Matching
    # ---------------------------------------------------------
    for alloc in allocations:
        if alloc.task_id in task_map and alloc.developer_id in team_map:
            task = task_map[alloc.task_id]
            dev = team_map[alloc.developer_id]
            if not is_dev_qualified(task_skill=task.skill_required, dev=dev, team=team):
                violations.append(
                    f"Skill mismatch violation: developer '{dev.id}' (skills: {dev.skills}) "
                    f"is not qualified for required skill '{task.skill_required}' of task '{task.id}'."
                )

    # ---------------------------------------------------------
    # Dimension 5: FTE Capacity Ceilings
    # ---------------------------------------------------------
    cap_result = calculate_team_capacity.func(
        team_profiles=team,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
    )
    capacities: dict[str, float] = cap_result["capacities"]

    for dev in team:
        dev_id = dev.id
        allocated_pts = allocated_by_dev[dev_id]
        max_cap = capacities.get(dev_id, 0.0)
        if allocated_pts > max_cap:
            violations.append(
                f"FTE capacity overflow violation: developer '{dev_id}' allocated {allocated_pts} points, "
                f"exceeding maximum capacity of {max_cap} points."
            )

    is_valid = len(violations) == 0
    is_feasible = is_valid

    if is_valid:
        summary = (
            f"Validation passed successfully: all {len(tasks)} tasks and {len(allocations)} allocations "
            f"comply with Anti-IDOR, DAG causality, skill matching, completeness, and FTE capacity ceilings."
        )
    else:
        summary = (
            f"Validation failed with {len(violations)} violation(s):\n"
            + "\n".join(f"- {v}" for v in violations)
        )

    return ValidationReport(
        is_valid=is_valid,
        is_feasible=is_feasible,
        violations=violations,
        allocated_by_dev=allocated_by_dev,
        capacities=capacities,
        summary=summary,
    )


def validation_node(
    state: SprintState,
    strict: bool = False,
    sprint_days: int = 10,
    points_per_day: float = 2.0,
) -> dict[str, Any]:
    """LangGraph node for the Deterministic Validation Agent (Validator Node).

    Audits the current SprintState against all formal business, capacity, and security constraints.
    - If valid: returns empty validation_errors [], clearing any errors from previous iterations.
    - If invalid and strict=True: raises ValueError with consolidated violations.
    - If invalid and strict=False: records violations in validation_errors for downstream supervision.

    Args:
        state: Shared SprintState blackboard.
        strict: If True, raises ValueError on any violation. If False, updates validation_errors.
        sprint_days: Sprint duration in business days (default: 10, must be > 0).
        points_per_day: Nominal story points rate per full-time day (default: 2.0, must be > 0).

    Returns:
        dict[str, Any]: State delta containing 'validation_errors' and 'messages'.

    Raises:
        ValueError: If inputs are invalid or if strict=True and audit detects violations.
    """
    report = audit_sprint_state(
        state=state,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
    )

    if strict and not report.is_valid:
        raise ValueError(
            f"Validation failed with {len(report.violations)} violation(s):\n"
            + "\n".join(f"- {v}" for v in report.violations)
        )

    status_str = "APPROVED" if report.is_valid else "REJECTED"
    ai_message = AIMessage(
        content=(
            f"### Validator Agent Deliberation\n\n"
            f"**Status**: {status_str}\n"
            f"**Feasible**: {report.is_feasible}\n"
            f"**Violations**: {len(report.violations)}\n\n"
            f"{report.summary}"
        )
    )

    return {
        "validation_errors": report.violations,
        "messages": [ai_message],
    }


# Official alias conforming to Phase 6 specifications
validator_node = validation_node
