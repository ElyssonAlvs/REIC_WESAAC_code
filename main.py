"""Executive CLI Entrypoint for the Sprint Planning Multi-Agent System (main.py)."""

import argparse
import json
import sys
import time
from typing import Any, Optional

from dotenv import load_dotenv

from sprint_mas.benchmarks import (
    BenchmarkConfig,
    export_benchmark_artifacts,
    format_benchmark_csv,
    format_benchmark_markdown,
    run_benchmark_suite,
    validate_safe_benchmark_path,
)
from sprint_mas.data_loader import list_available_scenarios, load_scenario
from sprint_mas.evaluation import (
    export_empirical_evaluation,
    format_empirical_evaluation_csv,
    format_empirical_evaluation_latex,
    format_empirical_evaluation_markdown,
    run_empirical_evaluation,
)
from sprint_mas.graph import run_sprint_planning
from sprint_mas.metrics_collector import (
    LangSmithMetricsSuiteReport,
    ModelScenarioMetric,
    export_metrics_artifacts,
    format_metrics_csv,
    format_metrics_latex,
    format_metrics_markdown,
    pull_langsmith_metrics,
)
from sprint_mas.replication import (
    ReplicationPackageConfig,
    ScientificReplicationBundle,
    export_replication_artifacts,
    format_replication_csv,
    format_replication_latex,
    format_replication_markdown,
    run_scientific_replication,
)
from sprint_mas.state import Allocation, DeveloperProfile, SprintPlan, Task
from sprint_mas.security_audit import (
    SecurityProbeResult,
    SemanticAlignmentResult,
    SecuritySemanticAuditReport,
    export_security_audit_artifacts,
    format_security_audit_markdown,
    run_pentagon_security_audit,
    sanitize_sprint_goal,
)
from sprint_mas.telemetry import (
    DeliberationTraceReport,
    configure_langsmith_tracing,
    extract_deliberation_trace,
    validate_safe_output_path,
)
from sprint_mas.tools import calculate_team_capacity

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def normalize_scenario_name(raw_scenario: str) -> str:
    """Normalizes scenario aliases ('a', 'b', 'c', 'scenario_a', etc.) and validates against the catalog.

    Args:
        raw_scenario: User-provided scenario string.

    Returns:
        str: Canonical scenario identifier (e.g., 'scenario_a').

    Raises:
        ValueError: If the scenario is empty or does not exist in data/processed/.
    """
    if not raw_scenario or not raw_scenario.strip():
        raise ValueError("Invalid scenario: scenario name cannot be empty.")

    cleaned = raw_scenario.strip().lower()
    if cleaned.endswith(".json"):
        cleaned = cleaned[:-5]
    if not cleaned.startswith("scenario_"):
        cleaned = f"scenario_{cleaned}"

    available = list_available_scenarios()
    if cleaned not in available:
        raise ValueError(
            f"Unknown scenario '{raw_scenario}'. Available scenarios: {', '.join(available)}."
        )

    return cleaned


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds the CLI ArgumentParser using Python standard library argparse."""
    parser = argparse.ArgumentParser(
        prog="sprint-mas",
        description="Sprint Planning Multi-Agent System (LangGraph BDI Architecture & LangSmith Observability)",
    )
    parser.add_argument(
        "-s",
        "--scenario",
        default="scenario_b",
        help="Experimental scenario to execute: a, b, c, scenario_a, scenario_b, or scenario_c (default: scenario_b).",
    )
    parser.add_argument(
        "-g",
        "--sprint-goal",
        default="Deliver highest business value tasks respecting DAG dependencies and team FTE capacity.",
        help="Executive sprint goal string.",
    )
    parser.add_argument(
        "-r",
        "--max-retries",
        type=int,
        default=2,
        help="Maximum corrective replanning retries for the circuit breaker (0 to 10, default: 2).",
    )
    parser.add_argument(
        "--sprint-days",
        type=int,
        default=10,
        help="Sprint duration in business days (must be > 0, default: 10).",
    )
    parser.add_argument(
        "--points-per-day",
        type=float,
        default=2.0,
        help="Nominal story points per full-time developer day (must be > 0, default: 2.0).",
    )
    parser.add_argument(
        "-t",
        "--thread-id",
        default="cli-session",
        help="LangGraph checkpoint session thread_id (default: cli-session).",
    )
    parser.add_argument(
        "--no-trim",
        action="store_true",
        help="Disable automatic capacity-based scope trimming during corrective replanning.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict LLM validation mode without deterministic fallbacks.",
    )
    parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Display the step-by-step BDI agent deliberation timeline.",
    )
    parser.add_argument(
        "--show-graph",
        action="store_true",
        help="Display the compiled LangGraph Mermaid state machine diagram.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit canonical JSON output to stdout instead of formatted tables.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Optional safe relative path inside the repository (.json, .md, or .csv) to save the execution report.",
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        action="store_true",
        help="Execute automated multi-run scientific benchmark suite.",
    )
    parser.add_argument(
        "-sc",
        "--scenarios",
        default="a,b,c",
        help="Comma-separated scenarios for benchmark execution (default: 'a,b,c').",
    )
    parser.add_argument(
        "-N",
        "--runs",
        type=int,
        default=1,
        help="Number of repetitions per scenario in benchmark mode (1 to 50, default: 1).",
    )
    parser.add_argument(
        "--offline-mock",
        action="store_true",
        help="Force offline deterministic execution without calling external LLM APIs.",
    )
    parser.add_argument(
        "--export-prefix",
        default=None,
        help="Prefix to automatically export benchmark suite artifacts (.json, .md, .csv) in reports/experiments/.",
    )
    parser.add_argument(
        "-e",
        "--evaluate-human",
        action="store_true",
        help="Executes empirical cross-paradigm evaluation comparing LangGraph BDI against legacy n8n and manual planning.",
    )
    parser.add_argument(
        "--security-audit",
        action="store_true",
        help="Executes automated Pentagon Defense security audit and semantic verification.",
    )
    parser.add_argument(
        "-R",
        "--reproduce-paper",
        "--replicate",
        dest="reproduce_paper",
        action="store_true",
        help="Executes 1-click end-to-end scientific replication suite for WESAAC 2025 and REIC 2026.",
    )
    parser.add_argument(
        "--sync-metrics",
        "--pull-langsmith",
        dest="sync_metrics",
        action="store_true",
        help="Sync and extract multi-model benchmark metrics directly from LangSmith API.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="LangSmith project name to extract metrics from (default: env LANGSMITH_PROJECT or 'REIC_WESAAC_code').",
    )
    return parser


def _compute_developer_loads(
    team: list[DeveloperProfile],
    allocations: list[Allocation],
    sprint_days: int,
    points_per_day: float,
) -> dict[str, dict[str, Any]]:
    """Calculates allocated points vs. analytical FTE capacity ceiling per developer."""
    cap_info = calculate_team_capacity.func(
        team_profiles=team,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
    )
    capacities = cap_info["capacities"]
    loads: dict[str, int] = {dev.id: 0 for dev in team}
    for alloc in allocations:
        if alloc.developer_id in loads:
            loads[alloc.developer_id] += alloc.allocated_points

    result: dict[str, dict[str, Any]] = {}
    for dev in team:
        cap = float(capacities.get(dev.id, 0.0))
        pts = loads.get(dev.id, 0)
        utilization = round((pts / cap) * 100.0, 1) if cap > 0 else 0.0
        result[dev.id] = {
            "name": dev.name,
            "fte": dev.fte,
            "skills": dev.skills,
            "allocated_points": pts,
            "capacity_ceiling": cap,
            "utilization_pct": utilization,
        }
    return result


def build_canonical_json_payload(
    state: dict[str, Any],
    trace: DeliberationTraceReport,
    tracing_info: dict[str, Any],
    team: list[DeveloperProfile],
    sprint_days: int,
    points_per_day: float,
) -> dict[str, Any]:
    """Constructs the canonical JSON-serializable dictionary for CLI output and artifact export."""
    sprint_plan: Optional[SprintPlan] = state.get("sprint_plan")
    validation_errors: list[str] = list(state.get("validation_errors") or [])
    allocations_raw = (
        sprint_plan.allocations
        if sprint_plan is not None
        else [
            a if isinstance(a, Allocation) else Allocation(**a)
            for a in (state.get("allocations") or [])
        ]
    )

    dev_loads = _compute_developer_loads(
        team=team,
        allocations=allocations_raw,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
    )

    return {
        "scenario": trace.scenario,
        "status": "APPROVED" if trace.is_approved else "REJECTED",
        "sprint_plan": sprint_plan.model_dump() if sprint_plan is not None else None,
        "validation_errors": validation_errors,
        "developer_loads": dev_loads,
        "trace": trace.model_dump(),
        "telemetry_config": {
            "tracing_enabled": tracing_info.get("tracing_enabled", False),
            "project_name": tracing_info.get("project_name", "sprint-planning-mas"),
            "api_key_masked": tracing_info.get("api_key_masked", ""),
            "reason": tracing_info.get("reason", ""),
        },
    }


def format_cli_report(
    state: dict[str, Any],
    trace: DeliberationTraceReport,
    tracing_info: dict[str, Any],
    team: list[DeveloperProfile],
    sprint_days: int = 10,
    points_per_day: float = 2.0,
    show_trace: bool = False,
    show_graph: bool = False,
) -> str:
    """Formats a human-readable executive report for terminal or Markdown inspection."""
    sprint_plan: Optional[SprintPlan] = state.get("sprint_plan")
    validation_errors: list[str] = list(state.get("validation_errors") or [])
    status_str = "APPROVED" if trace.is_approved else "REJECTED"

    allocations = (
        sprint_plan.allocations
        if sprint_plan is not None
        else [
            a if isinstance(a, Allocation) else Allocation(**a)
            for a in (state.get("allocations") or [])
        ]
    )
    tasks_list = (
        sprint_plan.tasks
        if sprint_plan is not None
        else [
            t if isinstance(t, Task) else Task(**t)
            for t in (state.get("prioritized_tasks") or state.get("backlog") or [])
        ]
    )
    task_map = {t.id: t for t in tasks_list}

    dev_loads = _compute_developer_loads(
        team=team,
        allocations=allocations,
        sprint_days=sprint_days,
        points_per_day=points_per_day,
    )

    lines: list[str] = [
        "=" * 88,
        f"SPRINT PLANNING MULTI-AGENT SYSTEM (BDI / LANGGRAPH) — STATUS: {status_str}",
        "=" * 88,
        f"Scenario            : {trace.scenario}",
        f"Thread ID           : {trace.thread_id}",
        f"Run ID              : {trace.run_id}",
        f"Execution Time      : {trace.execution_time_ms:.2f} ms",
        f"LangSmith Tracing   : {'ENABLED' if trace.langsmith_enabled else 'LOCAL FALLBACK'} "
        f"(project='{trace.langsmith_project}', reason='{tracing_info.get('reason', '')}')",
        f"Nodes Traversed     : {' -> '.join(trace.nodes_traversed)}",
        f"Validation Attempts : {trace.validation_attempts} | Replan Triggered: {trace.replan_triggered}",
        f"Allocated Scope     : {trace.total_tasks_allocated} tasks | {trace.total_points_allocated} story points",
        "-" * 88,
    ]

    if sprint_plan is not None:
        lines.append(f"Sprint Goal         : {sprint_plan.sprint_goal}")
        lines.append(f"Total Story Points  : {sprint_plan.total_points} pts ({len(sprint_plan.tasks)} tasks)")
        lines.append("-" * 88)
        lines.append("TASK ALLOCATIONS (CAUSAL & SKILL-MATCHED):")
        lines.append(
            f"{'Task ID':<10} | {'Developer':<10} | {'Pts':<5} | {'Skill':<10} | {'Prio':<4} | {'Dependencies'}"
        )
        lines.append("-" * 88)
        for alloc in sprint_plan.allocations:
            t_obj = task_map.get(alloc.task_id)
            skill = t_obj.skill_required if t_obj else "-"
            prio = str(t_obj.priority) if t_obj else "-"
            deps = ", ".join(t_obj.dependencies) if (t_obj and t_obj.dependencies) else "None"
            lines.append(
                f"{alloc.task_id:<10} | {alloc.developer_id:<10} | {alloc.allocated_points:<5} | "
                f"{skill:<10} | {prio:<4} | {deps}"
            )
        lines.append("-" * 88)

    lines.append("DEVELOPER FTE WORKLOAD vs. ANALYTICAL CAPACITY CEILING:")
    lines.append(
        f"{'Dev ID':<10} | {'Name':<14} | {'FTE':<5} | {'Allocated':<10} | {'Ceiling':<10} | {'Utilization'}"
    )
    lines.append("-" * 88)
    for dev_id, info in dev_loads.items():
        lines.append(
            f"{dev_id:<10} | {info['name']:<14} | {info['fte']:<5.1f} | "
            f"{info['allocated_points']:<10} | {info['capacity_ceiling']:<10.1f} | {info['utilization_pct']:.1f}%"
        )
    lines.append("-" * 88)

    if validation_errors:
        lines.append(f"GOVERNANCE VALIDATION VIOLATIONS ({len(validation_errors)}):")
        for err in validation_errors:
            lines.append(f"  - {err}")
        lines.append("-" * 88)

    if show_trace:
        lines.append("BDI DELIBERATION TRACE TIMELINE:")
        for step in trace.deliberation_steps:
            lines.append(
                f"  [{step.step_index}] node='{step.agent_node}' | bdi_phase='{step.bdi_phase}' | {step.headline}"
            )
            if step.content_preview:
                lines.append(f"      Preview: {step.content_preview}")
        lines.append("-" * 88)

    if show_graph:
        lines.append("COMPILED LANGGRAPH TOPOLOGY (MERMAID):")
        lines.append(trace.graph_mermaid.strip())
        lines.append("-" * 88)

    return "\n".join(lines)


def run_cli(argv: Optional[list[str]] = None) -> int:
    """Executes the Sprint Planning MAS CLI workflow and returns an OS exit code.

    Exit Codes:
        0: SprintPlan successfully approved with 0 governance violations.
        1: Invalid CLI arguments, missing scenario, or security violation.
        2: SprintPlan formally rejected by the Governance Supervisor (e.g., circuit breaker tripped).
    """
    load_dotenv(override=False)
    parser = build_arg_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return 0 if code == 0 else 1

    try:
        try:
            args.sprint_goal = sanitize_sprint_goal(args.sprint_goal)
        except ValueError as sec_err:
            print(f"CLI Security Error: {sec_err}", file=sys.stderr)
            return 1

        if args.reproduce_paper:
            if args.runs < 1 or args.runs > 50:
                raise ValueError(f"runs must be between 1 and 50, got {args.runs}.")
            if args.sprint_days <= 0:
                raise ValueError(f"sprint_days must be greater than 0, got {args.sprint_days}.")
            if args.points_per_day <= 0:
                raise ValueError(f"points_per_day must be greater than 0, got {args.points_per_day}.")
            if args.max_retries < 0 or args.max_retries > 10:
                raise ValueError(f"max_retries must be between 0 and 10, got {args.max_retries}.")
            if args.output:
                validate_safe_benchmark_path(args.output)

            raw_argv = argv if argv is not None else sys.argv[1:]
            has_single_scenario = any(arg in raw_argv for arg in ["-s", "--scenario"])
            if has_single_scenario:
                scenario_list = [args.scenario]
            else:
                scenario_list = [s.strip() for s in args.scenarios.split(",") if s.strip()]

            if not scenario_list:
                raise ValueError("Scenarios list cannot be empty.")

            repl_config = ReplicationPackageConfig(
                scenarios=scenario_list,
                runs=args.runs,
                offline_mock=args.offline_mock,
                max_retries=args.max_retries,
                sprint_days=args.sprint_days,
                points_per_day=args.points_per_day,
                enable_scope_trimming=not args.no_trim,
                strict=args.strict,
            )

            bundle = run_scientific_replication(config=repl_config)

            if args.export_prefix:
                export_replication_artifacts(bundle, base_filename=args.export_prefix)

            if args.output:
                safe_out = validate_safe_benchmark_path(args.output)
                safe_out.parent.mkdir(parents=True, exist_ok=True)
                if safe_out.suffix.lower() == ".json":
                    safe_out.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
                elif safe_out.suffix.lower() == ".csv":
                    safe_out.write_text(format_replication_csv(bundle), encoding="utf-8", newline="")
                elif safe_out.suffix.lower() == ".tex":
                    safe_out.write_text(format_replication_latex(bundle), encoding="utf-8")
                else:
                    safe_out.write_text(format_replication_markdown(bundle), encoding="utf-8")

            if args.json:
                print(bundle.model_dump_json(indent=2))
            else:
                print(format_replication_markdown(bundle))

            return 0 if bundle.is_fully_reproduced else 2

        if args.sync_metrics:
            if args.output:
                validate_safe_benchmark_path(args.output)

            report = pull_langsmith_metrics(project_name=args.project)

            if args.export_prefix:
                export_metrics_artifacts(report, base_filename=args.export_prefix)

            if args.output:
                safe_out = validate_safe_benchmark_path(args.output)
                safe_out.parent.mkdir(parents=True, exist_ok=True)
                if safe_out.suffix.lower() == ".json":
                    safe_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
                elif safe_out.suffix.lower() == ".csv":
                    safe_out.write_text(format_metrics_csv(report), encoding="utf-8", newline="")
                elif safe_out.suffix.lower() == ".tex":
                    safe_out.write_text(format_metrics_latex(report), encoding="utf-8")
                else:
                    safe_out.write_text(format_metrics_markdown(report), encoding="utf-8")

            if args.json:
                print(report.model_dump_json(indent=2))
            else:
                print(format_metrics_markdown(report))

            return 0 if report.all_passed else 2

        if args.security_audit:
            if args.output:
                validate_safe_benchmark_path(args.output)

            report = run_pentagon_security_audit()

            if args.export_prefix:
                export_security_audit_artifacts(report, export_prefix=args.export_prefix)

            if args.output:
                safe_out = validate_safe_benchmark_path(args.output)
                safe_out.parent.mkdir(parents=True, exist_ok=True)
                if safe_out.suffix.lower() == ".json":
                    safe_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
                else:
                    safe_out.write_text(format_security_audit_markdown(report), encoding="utf-8")

            if args.json:
                print(report.model_dump_json(indent=2))
            else:
                print(format_security_audit_markdown(report))

            return 0 if report.all_passed else 2

        if args.evaluate_human:
            if args.runs < 1 or args.runs > 50:
                raise ValueError(f"runs must be between 1 and 50, got {args.runs}.")
            if args.sprint_days <= 0:
                raise ValueError(f"sprint_days must be greater than 0, got {args.sprint_days}.")
            if args.points_per_day <= 0:
                raise ValueError(f"points_per_day must be greater than 0, got {args.points_per_day}.")
            if args.max_retries < 0 or args.max_retries > 10:
                raise ValueError(f"max_retries must be between 0 and 10, got {args.max_retries}.")
            if args.output:
                validate_safe_benchmark_path(args.output)

            raw_argv = argv if argv is not None else sys.argv[1:]
            has_single_scenario = any(arg in raw_argv for arg in ["-s", "--scenario"])
            if has_single_scenario:
                scenario_list = [args.scenario]
            else:
                scenario_list = [s.strip() for s in args.scenarios.split(",") if s.strip()]

            if not scenario_list:
                raise ValueError("Scenarios list cannot be empty.")

            eval_config = BenchmarkConfig(
                scenarios=scenario_list,
                runs=args.runs,
                offline_mock=args.offline_mock,
                max_retries=args.max_retries,
                sprint_days=args.sprint_days,
                points_per_day=args.points_per_day,
                enable_scope_trimming=not args.no_trim,
                strict=args.strict,
            )

            eval_report = run_empirical_evaluation(config=eval_config)

            if args.export_prefix:
                export_empirical_evaluation(eval_report, base_filename=args.export_prefix)

            if args.output:
                safe_out = validate_safe_benchmark_path(args.output)
                safe_out.parent.mkdir(parents=True, exist_ok=True)
                if safe_out.suffix.lower() == ".json":
                    safe_out.write_text(eval_report.model_dump_json(indent=2), encoding="utf-8")
                elif safe_out.suffix.lower() == ".csv":
                    safe_out.write_text(format_empirical_evaluation_csv(eval_report), encoding="utf-8", newline="")
                elif safe_out.suffix.lower() == ".tex":
                    safe_out.write_text(format_empirical_evaluation_latex(eval_report), encoding="utf-8")
                else:
                    safe_out.write_text(format_empirical_evaluation_markdown(eval_report), encoding="utf-8")

            if args.json:
                print(eval_report.model_dump_json(indent=2))
            else:
                print(format_empirical_evaluation_markdown(eval_report))

            all_approved = all(c.langgraph_success_rate_pct == 100.0 for c in eval_report.comparisons)
            return 0 if all_approved else 2

        if args.benchmark:
            if args.runs < 1 or args.runs > 50:
                raise ValueError(f"runs must be between 1 and 50, got {args.runs}.")
            if args.sprint_days <= 0:
                raise ValueError(f"sprint_days must be greater than 0, got {args.sprint_days}.")
            if args.points_per_day <= 0:
                raise ValueError(f"points_per_day must be greater than 0, got {args.points_per_day}.")
            if args.max_retries < 0 or args.max_retries > 10:
                raise ValueError(f"max_retries must be between 0 and 10, got {args.max_retries}.")

            scenario_list = [s.strip() for s in args.scenarios.split(",") if s.strip()]
            if not scenario_list:
                raise ValueError("Scenarios list cannot be empty.")

            bench_config = BenchmarkConfig(
                scenarios=scenario_list,
                runs=args.runs,
                offline_mock=args.offline_mock,
                max_retries=args.max_retries,
                sprint_days=args.sprint_days,
                points_per_day=args.points_per_day,
                enable_scope_trimming=not args.no_trim,
                strict=args.strict,
            )

            report = run_benchmark_suite(config=bench_config)

            if args.export_prefix:
                export_benchmark_artifacts(report, base_filename=args.export_prefix)

            if args.output:
                safe_out = validate_safe_benchmark_path(args.output)
                safe_out.parent.mkdir(parents=True, exist_ok=True)
                if safe_out.suffix.lower() == ".json":
                    safe_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
                elif safe_out.suffix.lower() == ".csv":
                    safe_out.write_text(format_benchmark_csv(report), encoding="utf-8", newline="")
                else:
                    safe_out.write_text(format_benchmark_markdown(report), encoding="utf-8")

            if args.json:
                print(report.model_dump_json(indent=2))
            else:
                print(format_benchmark_markdown(report))

            return 0 if report.all_approved else 2

        normalized_scenario = normalize_scenario_name(args.scenario)
        if args.max_retries < 0 or args.max_retries > 10:
            raise ValueError(f"max_retries must be between 0 and 10, got {args.max_retries}.")
        if args.sprint_days <= 0:
            raise ValueError(f"sprint_days must be greater than 0, got {args.sprint_days}.")
        if args.points_per_day <= 0:
            raise ValueError(f"points_per_day must be greater than 0, got {args.points_per_day}.")

        safe_output_path = (
            validate_safe_output_path(args.output)
            if args.output is not None
            else None
        )

        tracing_info = configure_langsmith_tracing()
        tasks, team = load_scenario(normalized_scenario)

        start_ns = time.perf_counter()
        final_state = run_sprint_planning(
            backlog=tasks,
            team=team,
            thread_id=args.thread_id,
            sprint_goal=args.sprint_goal,
            strict=args.strict,
            max_retries=args.max_retries,
            sprint_days=args.sprint_days,
            points_per_day=args.points_per_day,
            enable_scope_trimming=not args.no_trim,
            scenario_name=normalized_scenario,
        )
        elapsed_ms = (time.perf_counter() - start_ns) * 1000.0

        trace = extract_deliberation_trace(
            state=final_state,
            scenario=normalized_scenario,
            thread_id=args.thread_id,
            execution_time_ms=elapsed_ms,
            langsmith_enabled=bool(tracing_info.get("tracing_enabled", False)),
            langsmith_project=str(tracing_info.get("project_name", "sprint-planning-mas")),
        )

        json_payload = build_canonical_json_payload(
            state=final_state,
            trace=trace,
            tracing_info=tracing_info,
            team=team,
            sprint_days=args.sprint_days,
            points_per_day=args.points_per_day,
        )

        text_report = format_cli_report(
            state=final_state,
            trace=trace,
            tracing_info=tracing_info,
            team=team,
            sprint_days=args.sprint_days,
            points_per_day=args.points_per_day,
            show_trace=args.show_trace,
            show_graph=args.show_graph,
        )

        if safe_output_path is not None:
            safe_output_path.parent.mkdir(parents=True, exist_ok=True)
            if safe_output_path.suffix.lower() == ".json":
                safe_output_path.write_text(
                    json.dumps(json_payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                safe_output_path.write_text(text_report, encoding="utf-8")

        if args.json:
            print(json.dumps(json_payload, indent=2, ensure_ascii=False))
        else:
            print(text_report)

        return 0 if trace.is_approved else 2

    except Exception as exc:
        print(f"CLI Execution Error: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    """Entrypoint when invoked directly via `python main.py`."""
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
