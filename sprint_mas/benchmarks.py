"""Automated Scientific Benchmark Suite for Sprint Planning MAS (sprint_mas/benchmarks.py).

Provides deterministic and live multi-run scenario benchmarking, server-side compliance verification,
statistical metrics calculation (mean, std, median, min, max, p95), and safe artifact export (.json, .md, .csv).
"""

import csv
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import statistics
import time
from typing import Any, Optional, Union
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sprint_mas.agents.validator import audit_sprint_state
from sprint_mas.data_loader import list_available_scenarios, load_scenario
from sprint_mas.graph import OfflineFallbackChatModel, run_sprint_planning
from sprint_mas.llm_factory import get_llm
from sprint_mas.telemetry import extract_deliberation_trace
from sprint_mas.tools import calculate_team_capacity


def normalize_scenario_name(raw_scenario: str) -> str:
    """Normalizes scenario aliases ('a', 'b', 'c', 'scenario_a', etc.) and validates against the catalog.

    Args:
        raw_scenario: User-provided scenario string.

    Returns:
        str: Canonical scenario identifier (e.g., 'scenario_a').

    Raises:
        ValueError: If the scenario is empty or does not exist in data/processed/.
    """
    if not raw_scenario or not str(raw_scenario).strip():
        raise ValueError("Invalid scenario: scenario name cannot be empty.")

    cleaned = str(raw_scenario).strip().lower()
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


class BenchmarkConfig(BaseModel):
    """Immutable execution configuration for benchmark experiments."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[str] = Field(
        default=["scenario_a", "scenario_b", "scenario_c"],
        description="List of canonical or aliased scenario names to benchmark.",
    )
    runs: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Number of benchmark repetitions per scenario (1 to 50).",
    )
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider name ('groq', 'ollama', or 'offline').",
    )
    model: Optional[str] = Field(
        default=None,
        description="Specific model identifier to use.",
    )
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature for the LLM.",
    )
    offline_mock: bool = Field(
        default=False,
        description="Forces offline deterministic fallback execution without external API calls.",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Maximum circuit breaker retries for replanning.",
    )
    sprint_days: int = Field(
        default=10,
        gt=0,
        description="Sprint duration in business days.",
    )
    points_per_day: float = Field(
        default=2.0,
        gt=0.0,
        description="Nominal story point rate per full-time developer day.",
    )
    enable_scope_trimming: bool = Field(
        default=True,
        description="Whether to perform capacity-based scope trimming during replan.",
    )
    strict: bool = Field(
        default=False,
        description="Strict mode without deterministic agent fallbacks.",
    )

    @field_validator("scenarios", mode="before")
    @classmethod
    def _validate_and_normalize_scenarios(cls, v: Any) -> list[str]:
        if not v:
            raise ValueError("Scenarios list cannot be empty.")
        if not isinstance(v, list):
            raise ValueError("Scenarios must be provided as a list.")
        normalized = []
        for item in v:
            normalized.append(normalize_scenario_name(str(item)))
        return normalized


class ScenarioRunMetric(BaseModel):
    """Execution telemetry captured for an individual benchmark run."""

    model_config = ConfigDict(extra="forbid")

    run_index: int = Field(..., description="1-based index of this repetition.")
    scenario: str = Field(..., description="Canonical scenario name.")
    thread_id: str = Field(..., description="Unique isolated session thread_id.")
    execution_time_ms: float = Field(..., description="Wall-clock execution time in milliseconds.")
    approved: bool = Field(..., description="True if sprint plan was approved by supervisor.")
    total_tasks: int = Field(..., description="Total tasks present in backlog.")
    allocated_tasks: int = Field(..., description="Number of tasks scheduled in sprint.")
    total_points: int = Field(..., description="Total backlog story points.")
    allocated_points: int = Field(..., description="Total story points scheduled in sprint.")
    team_capacity: float = Field(..., description="Analytical team capacity ceiling.")
    utilization_pct: float = Field(..., description="Percentage of team capacity utilized.")
    validation_attempts: int = Field(..., description="Number of validation passes in graph.")
    replan_triggered: bool = Field(..., description="True if corrective replan node was executed.")
    dag_violations: int = Field(..., description="Count of DAG causality violations detected.")
    fte_violations: int = Field(..., description="Count of developer capacity overruns detected.")
    skill_violations: int = Field(..., description="Count of skill mismatch violations detected.")
    llm_fallback_triggered: bool = Field(..., description="True if neuro-symbolic deterministic fallback was activated.")
    nodes_traversed: list[str] = Field(..., description="Ordered list of LangGraph nodes executed.")


class ScenarioBenchmarkSummary(BaseModel):
    """Consolidated statistical summary across all runs for a single scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(..., description="Canonical scenario name.")
    total_runs: int = Field(..., description="Total repetitions executed.")
    successful_runs: int = Field(..., description="Number of runs resulting in approved plan.")
    approval_rate: float = Field(..., description="Ratio of successful runs (0.0 to 1.0).")
    mean_time_ms: float = Field(..., description="Mean execution time in ms.")
    std_time_ms: float = Field(..., description="Standard deviation of execution time (0.0 if runs=1).")
    median_time_ms: float = Field(..., description="Median execution time in ms.")
    min_time_ms: float = Field(..., description="Minimum execution time in ms.")
    max_time_ms: float = Field(..., description="Maximum execution time in ms.")
    p95_time_ms: float = Field(..., description="95th percentile execution time in ms.")
    mean_allocated_points: float = Field(..., description="Average story points scheduled.")
    mean_utilization_pct: float = Field(..., description="Average team capacity utilization percentage.")
    replan_rate: float = Field(..., description="Ratio of runs that triggered corrective replan.")
    dag_violations_total: int = Field(..., description="Cumulative DAG violations across all runs.")
    fte_violations_total: int = Field(..., description="Cumulative FTE capacity violations across all runs.")
    skill_violations_total: int = Field(..., description="Cumulative skill violations across all runs.")
    runs_metrics: list[ScenarioRunMetric] = Field(..., description="Detailed per-run telemetry records.")


class BenchmarkSuiteReport(BaseModel):
    """Final immutable report consolidating benchmark results across all configured scenarios."""

    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(..., description="Unique suite execution identifier.")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of execution.")
    config: BenchmarkConfig = Field(..., description="Benchmark suite execution parameters.")
    provider: str = Field(..., description="Active LLM provider name.")
    model: str = Field(..., description="Active model name.")
    summaries: list[ScenarioBenchmarkSummary] = Field(..., description="Per-scenario summaries.")
    total_execution_time_ms: float = Field(..., description="Total wall-clock execution time in ms.")
    all_approved: bool = Field(..., description="True if 100% of runs in all scenarios were approved.")


def run_scenario_benchmark(
    scenario_name: str,
    config: Optional[BenchmarkConfig] = None,
    llm: Optional[Any] = None,
) -> ScenarioBenchmarkSummary:
    """Executes a benchmark experiment for a single scenario across N repetitions.

    Args:
        scenario_name: Target scenario name or alias (e.g. 'a', 'scenario_b').
        config: BenchmarkConfig instance. If None, default configuration is used.
        llm: Optional pre-configured LLM instance.

    Returns:
        ScenarioBenchmarkSummary: Statistical summary and per-run telemetry.
    """
    cfg = config or BenchmarkConfig()
    canonical_scn = normalize_scenario_name(scenario_name)
    tasks, team = load_scenario(canonical_scn)

    cap_res = calculate_team_capacity.func(
        team_profiles=team,
        sprint_days=cfg.sprint_days,
        points_per_day=cfg.points_per_day,
    )
    team_cap_val = float(sum(cap_res["capacities"].values()))
    total_pts = sum(t.story_points for t in tasks)
    total_tasks = len(tasks)

    resolved_llm = llm
    if resolved_llm is None and cfg.offline_mock:
        resolved_llm = OfflineFallbackChatModel()
    elif resolved_llm is None and cfg.provider == "offline":
        resolved_llm = OfflineFallbackChatModel()
    elif resolved_llm is None and (cfg.provider or cfg.model):
        resolved_llm = get_llm(
            provider=cfg.provider,
            model=cfg.model,
            temperature=cfg.temperature,
        )

    runs_metrics: list[ScenarioRunMetric] = []

    for i in range(1, cfg.runs + 1):
        thread_id = f"bench-{canonical_scn}-run{i}-{uuid.uuid4().hex[:8]}"
        start_ns = time.perf_counter()
        final_state = run_sprint_planning(
            backlog=tasks,
            team=team,
            llm=resolved_llm,
            thread_id=thread_id,
            strict=cfg.strict,
            max_retries=cfg.max_retries,
            sprint_days=cfg.sprint_days,
            points_per_day=cfg.points_per_day,
            enable_scope_trimming=cfg.enable_scope_trimming,
            scenario_name=canonical_scn,
        )
        elapsed_ms = (time.perf_counter() - start_ns) * 1000.0

        audit_report = audit_sprint_state(
            final_state,
            sprint_days=cfg.sprint_days,
            points_per_day=cfg.points_per_day,
        )
        trace = extract_deliberation_trace(
            state=final_state,
            scenario=canonical_scn,
            thread_id=thread_id,
            execution_time_ms=elapsed_ms,
        )

        sprint_plan = final_state.get("sprint_plan")
        if sprint_plan is not None:
            allocated_tasks = len(sprint_plan.tasks)
            allocated_pts = sprint_plan.total_points
        else:
            allocated_tasks = 0
            allocated_pts = 0

        utilization_pct = round(
            (allocated_pts / team_cap_val * 100.0) if team_cap_val > 0 else 0.0,
            2,
        )

        dag_violations = sum(
            1
            for v in audit_report.violations
            if any(k in v.lower() for k in ["dag", "dependenc", "inversion", "circular", "orphan"])
        )
        fte_violations = sum(
            1
            for v in audit_report.violations
            if any(k in v.lower() for k in ["fte", "capacity overflow", "exceeding maximum capacity"])
        )
        skill_violations = sum(
            1
            for v in audit_report.violations
            if any(k in v.lower() for k in ["skill", "qualifi"])
        )

        fallback_triggered = (
            cfg.offline_mock
            or isinstance(resolved_llm, OfflineFallbackChatModel)
            or any(
                "Fallback Determinístico Ativado" in str(getattr(m, "content", ""))
                for m in final_state.get("messages", [])
            )
        )

        metric = ScenarioRunMetric(
            run_index=i,
            scenario=canonical_scn,
            thread_id=thread_id,
            execution_time_ms=round(elapsed_ms, 2),
            approved=trace.is_approved,
            total_tasks=total_tasks,
            allocated_tasks=allocated_tasks,
            total_points=total_pts,
            allocated_points=allocated_pts,
            team_capacity=round(team_cap_val, 1),
            utilization_pct=utilization_pct,
            validation_attempts=trace.validation_attempts,
            replan_triggered=trace.replan_triggered,
            dag_violations=dag_violations,
            fte_violations=fte_violations,
            skill_violations=skill_violations,
            llm_fallback_triggered=fallback_triggered,
            nodes_traversed=trace.nodes_traversed,
        )
        runs_metrics.append(metric)

    times = [m.execution_time_ms for m in runs_metrics]
    total_runs = len(runs_metrics)
    successful_runs = sum(1 for m in runs_metrics if m.approved)
    approval_rate = round(successful_runs / total_runs, 4) if total_runs > 0 else 0.0

    mean_time = round(statistics.mean(times), 2)
    std_time = round(statistics.stdev(times), 2) if len(times) > 1 else 0.0
    median_time = round(statistics.median(times), 2)
    min_time = round(min(times), 2)
    max_time = round(max(times), 2)

    if len(times) == 1:
        p95_time = times[0]
    else:
        sorted_times = sorted(times)
        rank = 0.95 * (len(sorted_times) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_times) - 1)
        weight = rank - lower
        p95_time = round(
            sorted_times[lower] * (1.0 - weight) + sorted_times[upper] * weight,
            2,
        )

    mean_pts = round(statistics.mean(m.allocated_points for m in runs_metrics), 1)
    mean_util = round(statistics.mean(m.utilization_pct for m in runs_metrics), 1)
    replan_rate = round(sum(1 for m in runs_metrics if m.replan_triggered) / total_runs, 4)

    return ScenarioBenchmarkSummary(
        scenario=canonical_scn,
        total_runs=total_runs,
        successful_runs=successful_runs,
        approval_rate=approval_rate,
        mean_time_ms=mean_time,
        std_time_ms=std_time,
        median_time_ms=median_time,
        min_time_ms=min_time,
        max_time_ms=max_time,
        p95_time_ms=p95_time,
        mean_allocated_points=mean_pts,
        mean_utilization_pct=mean_util,
        replan_rate=replan_rate,
        dag_violations_total=sum(m.dag_violations for m in runs_metrics),
        fte_violations_total=sum(m.fte_violations for m in runs_metrics),
        skill_violations_total=sum(m.skill_violations for m in runs_metrics),
        runs_metrics=runs_metrics,
    )


def run_benchmark_suite(
    config: Optional[BenchmarkConfig] = None,
    llm: Optional[Any] = None,
) -> BenchmarkSuiteReport:
    """Executes the benchmark suite across all configured scenarios and aggregates the results.

    Args:
        config: BenchmarkConfig instance.
        llm: Optional pre-configured LLM instance.

    Returns:
        BenchmarkSuiteReport: Comprehensive suite execution report.
    """
    cfg = config or BenchmarkConfig()
    suite_id = f"bench-{uuid.uuid4().hex[:8]}"
    start_ns = time.perf_counter()

    resolved_llm = OfflineFallbackChatModel() if cfg.offline_mock else llm

    summaries: list[ScenarioBenchmarkSummary] = []
    for scn in cfg.scenarios:
        summary = run_scenario_benchmark(
            scenario_name=scn,
            config=cfg,
            llm=resolved_llm,
        )
        summaries.append(summary)

    total_time_ms = round((time.perf_counter() - start_ns) * 1000.0, 2)
    all_approved = all(s.approval_rate == 1.0 for s in summaries) if summaries else False

    provider_name = cfg.provider or ("offline" if cfg.offline_mock else os.getenv("PROVIDER", "groq"))
    model_name = cfg.model or ("deterministic-fallback" if cfg.offline_mock else os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))

    return BenchmarkSuiteReport(
        suite_id=suite_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        config=cfg,
        provider=provider_name,
        model=model_name,
        summaries=summaries,
        total_execution_time_ms=total_time_ms,
        all_approved=all_approved,
    )


def format_benchmark_markdown(report: BenchmarkSuiteReport) -> str:
    """Formats the benchmark suite report as a publication-ready GitHub Markdown table.

    Args:
        report: BenchmarkSuiteReport to format.

    Returns:
        str: Markdown document with tabular results.
    """
    lines = [
        f"# Benchmark Suite Report: {report.suite_id}",
        f"**Timestamp:** {report.timestamp} | **Provider:** {report.provider} | **Model:** {report.model} | **Runs per Scenario:** {report.config.runs}",
        "",
        "| Cenário | Tarefas (Total/Alocadas) | Pontos (Alocados/Capacidade) | Utilização % | Tentativas | Replan? | Violações (DAG/FTE/Skill) | Tempo Médio (ms) | P95 (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for s in report.summaries:
        m0 = s.runs_metrics[0] if s.runs_metrics else None
        tot_t = m0.total_tasks if m0 else 0
        alloc_t = int(round(statistics.mean(m.allocated_tasks for m in s.runs_metrics))) if s.runs_metrics else 0
        cap = m0.team_capacity if m0 else 0.0
        pts = s.mean_allocated_points
        util = s.mean_utilization_pct
        attempts = round(statistics.mean(m.validation_attempts for m in s.runs_metrics), 1) if s.runs_metrics else 1.0
        replan_str = "Sim" if s.replan_rate > 0 else "Não"
        viols_str = f"{s.dag_violations_total}/{s.fte_violations_total}/{s.skill_violations_total}"
        lines.append(
            f"| {s.scenario} | {tot_t}/{alloc_t} | {pts:.1f}/{cap:.1f} | {util:.1f}% | {attempts:.1f} | {replan_str} | {viols_str} | {s.mean_time_ms:.2f} | {s.p95_time_ms:.2f} |"
        )

    lines.append("")
    approved_count = sum(1 for s in report.summaries if s.approval_rate == 1.0)
    status_str = "APPROVED" if report.all_approved else "REJECTED"
    lines.append(
        f"**STATUS GERAL: {status_str}** ({approved_count}/{len(report.summaries)} cenários aprovados com 100% de conformidade, tempo total: {report.total_execution_time_ms:.2f} ms)"
    )
    return "\n".join(lines)


def format_benchmark_csv(report: BenchmarkSuiteReport) -> str:
    """Formats the individual benchmark run metrics as a standard RFC 4180 CSV string.

    Args:
        report: BenchmarkSuiteReport to format.

    Returns:
        str: CSV string.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    headers = [
        "suite_id",
        "scenario",
        "run_index",
        "thread_id",
        "execution_time_ms",
        "approved",
        "total_tasks",
        "allocated_tasks",
        "total_points",
        "allocated_points",
        "team_capacity",
        "utilization_pct",
        "validation_attempts",
        "replan_triggered",
        "dag_violations",
        "fte_violations",
        "skill_violations",
        "llm_fallback_triggered",
        "nodes_traversed",
    ]
    writer.writerow(headers)

    for s in report.summaries:
        for m in s.runs_metrics:
            writer.writerow([
                report.suite_id,
                m.scenario,
                m.run_index,
                m.thread_id,
                m.execution_time_ms,
                m.approved,
                m.total_tasks,
                m.allocated_tasks,
                m.total_points,
                m.allocated_points,
                m.team_capacity,
                m.utilization_pct,
                m.validation_attempts,
                m.replan_triggered,
                m.dag_violations,
                m.fte_violations,
                m.skill_violations,
                m.llm_fallback_triggered,
                ";".join(m.nodes_traversed),
            ])

    return output.getvalue()


def validate_safe_benchmark_path(
    path: Union[str, Path],
    base_dir: Optional[Path] = None,
) -> Path:
    """Validates that a path is safe against Path Traversal and restricted to allowed extensions (.json, .md, .csv, .tex).

    Args:
        path: Relative or absolute path to validate.
        base_dir: Allowed base directory (defaults to repository root).

    Returns:
        Path: Resolved absolute path.

    Raises:
        ValueError: If path is empty, escapes base directory, or has a forbidden extension.
    """
    if path is None or not str(path).strip():
        raise ValueError("Security violation: path cannot be empty.")

    base = base_dir.resolve() if base_dir is not None else Path(__file__).resolve().parent.parent.resolve()
    raw_p = Path(path)

    allowed_extensions = {".json", ".md", ".csv", ".tex"}
    if raw_p.suffix.lower() not in allowed_extensions:
        raise ValueError(
            f"Security violation: forbidden extension '{raw_p.suffix}'. Allowed extensions: .json, .md, .csv, .tex"
        )

    if raw_p.is_absolute():
        target = raw_p.resolve()
    else:
        target = (base / raw_p).resolve()

    try:
        is_rel = target.is_relative_to(base)
    except AttributeError:
        is_rel = str(target).startswith(str(base))

    if not is_rel:
        raise ValueError(
            f"Security violation: path escapes repository base directory '{base}'."
        )

    return target


def export_benchmark_artifacts(
    report: BenchmarkSuiteReport,
    base_filename: str,
    output_dir: Optional[Union[str, Path]] = None,
    export_json: bool = True,
    export_md: bool = True,
    export_csv: bool = True,
) -> dict[str, Path]:
    """Safely exports benchmark suite artifacts in .json, .md, and .csv formats.

    Args:
        report: BenchmarkSuiteReport to export.
        base_filename: Base filename without extension (or prefix).
        output_dir: Output directory relative to repository root or absolute.
        export_json: Whether to export .json artifact.
        export_md: Whether to export .md artifact.
        export_csv: Whether to export .csv artifact.

    Returns:
        dict[str, Path]: Map of format identifier ('json', 'md', 'csv') to written Path.
    """
    repo_root = Path(__file__).resolve().parent.parent.resolve()
    out_dir_path = Path(output_dir) if output_dir else Path("reports/experiments")
    if not out_dir_path.is_absolute():
        out_dir_path = (repo_root / out_dir_path).resolve()
    else:
        out_dir_path = out_dir_path.resolve()

    out_dir_path.mkdir(parents=True, exist_ok=True)

    clean_base = base_filename
    for sfx in [".json", ".md", ".csv"]:
        if clean_base.lower().endswith(sfx):
            clean_base = clean_base[:-len(sfx)]

    artifacts: dict[str, Path] = {}

    if export_json:
        target_json = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.json", base_dir=repo_root)
        target_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        artifacts["json"] = target_json

    if export_md:
        target_md = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.md", base_dir=repo_root)
        target_md.write_text(format_benchmark_markdown(report), encoding="utf-8")
        artifacts["md"] = target_md

    if export_csv:
        target_csv = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.csv", base_dir=repo_root)
        target_csv.write_text(format_benchmark_csv(report), encoding="utf-8")
        artifacts["csv"] = target_csv

    return artifacts
