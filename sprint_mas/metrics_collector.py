"""Automated Metrics Extractor and Multi-Model Consolidation via LangSmith API (sprint_mas/metrics_collector.py).

Provides read-only extraction of empirical multi-agent sprint planning runs from LangSmith,
resilient handling of API rate limits and authentication errors, multi-model statistical aggregation,
and safe multi-format artifact export (.json, .md, .csv, .tex).
"""

import csv
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import re
import statistics
import time
from typing import Any, Optional, Union
import uuid

from pydantic import BaseModel, ConfigDict, Field

try:
    import langsmith
    from langsmith import Client as LangSmithClient
    from langsmith.utils import (
        LangSmithAuthError,
        LangSmithError,
        LangSmithRateLimitError,
    )
except ImportError:
    langsmith = None
    LangSmithClient = None
    LangSmithAuthError = Exception
    LangSmithError = Exception
    LangSmithRateLimitError = Exception

from sprint_mas.benchmarks import validate_safe_benchmark_path


class ModelScenarioMetric(BaseModel):
    """Aggregated empirical benchmark metrics for a specific model in a scenario."""

    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(..., description="Canonical LLM identifier (e.g. 'openai/gpt-oss-120b').")
    scenario: str = Field(..., description="Canonical scenario identifier (e.g. 'scenario_b').")
    runs_count: int = Field(..., ge=0, description="Total number of evaluated runs.")
    mean_duration_ms: float = Field(..., ge=0.0, description="Arithmetic mean execution latency in milliseconds.")
    median_duration_ms: float = Field(..., ge=0.0, description="Median execution latency in milliseconds.")
    p95_duration_ms: float = Field(..., ge=0.0, description="95th percentile execution latency in milliseconds.")
    mean_prompt_tokens: float = Field(..., ge=0.0, description="Mean input/prompt tokens per run.")
    mean_completion_tokens: float = Field(..., ge=0.0, description="Mean output/completion tokens per run.")
    mean_total_tokens: float = Field(..., ge=0.0, description="Mean total tokens per run.")
    total_cost_usd: float = Field(..., ge=0.0, description="Accumulated financial cost in USD across all runs.")
    success_rate_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of runs completed successfully.")


class LangSmithMetricsSuiteReport(BaseModel):
    """Consolidated suite report extracted from LangSmith API runs."""

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(..., description="Unique report execution identifier.")
    project_name: str = Field(..., description="Queried LangSmith project name.")
    extracted_at: str = Field(..., description="ISO 8601 UTC timestamp of metric extraction.")
    total_runs_analyzed: int = Field(..., ge=0, description="Total number of relevant runs extracted and analyzed.")
    metrics: list[ModelScenarioMetric] = Field(
        default_factory=list, description="Aggregated metrics grouped by model and scenario."
    )
    all_passed: bool = Field(default=True, description="True if extraction succeeded and runs passed validation.")
    notes: list[str] = Field(default_factory=list, description="Operational notes, warnings, or error descriptions.")


# ---------------------------------------------------------------------------
# Run Parsing and Metadata Extraction Helpers
# ---------------------------------------------------------------------------


def _extract_scenario(run: Any) -> Optional[str]:
    """Extracts and normalizes the scenario identifier from a LangSmith run object."""
    # 1. From run tags (highest specificity for LangSmith BDI runs)
    tags = getattr(run, "tags", None) or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("scenario:"):
                raw = tag.split("scenario:", 1)[1].strip().lower()
                if raw == "custom":
                    continue
                if raw.endswith(".json"):
                    raw = raw[:-5]
                if not raw.startswith("scenario_") and raw in {"a", "b", "c"}:
                    raw = f"scenario_{raw}"
                return raw

    # 2. From run name
    name = getattr(run, "name", "") or ""
    if isinstance(name, str):
        match = re.search(r"scenario[_-]?([abc])\b", name.lower())
        if match:
            return f"scenario_{match.group(1)}"
        if "scenario_a" in name.lower() or "scenario-a" in name.lower():
            return "scenario_a"
        if "scenario_b" in name.lower() or "scenario-b" in name.lower():
            return "scenario_b"
        if "scenario_c" in name.lower() or "scenario-c" in name.lower():
            return "scenario_c"

    # 3. From run metadata
    metadata = getattr(run, "metadata", None)
    if not isinstance(metadata, dict):
        extra = getattr(run, "extra", None)
        if isinstance(extra, dict):
            metadata = extra.get("metadata")
    if isinstance(metadata, dict):
        scn = metadata.get("scenario")
        if scn and isinstance(scn, str):
            cleaned = scn.strip().lower()
            if cleaned != "custom":
                if cleaned.endswith(".json"):
                    cleaned = cleaned[:-5]
                if not cleaned.startswith("scenario_") and cleaned in {"a", "b", "c"}:
                    cleaned = f"scenario_{cleaned}"
                return cleaned

    # 4. From inputs (prompts/messages content inference)
    inputs = getattr(run, "inputs", None)
    if isinstance(inputs, dict):
        txt = str(inputs.get("messages") or inputs.get("prompts") or inputs)
        if "TSK-001" in txt or "TSK-002" in txt or "scenario_a" in txt.lower():
            return "scenario_a"
        if "TSK-101" in txt or "TSK-102" in txt or "scenario_b" in txt.lower():
            return "scenario_b"
        if "TSK-201" in txt or "TSK-202" in txt or "scenario_c" in txt.lower():
            return "scenario_c"

    return None


def _is_sprint_mas_run(run: Any) -> bool:
    """Verifies whether a LangSmith run belongs to the sprint-mas evaluation domain."""
    name = getattr(run, "name", "") or ""
    if name == "OfflineFallbackChatModel":
        return False

    model_name = _extract_model_name(run)
    if model_name == "OfflineFallbackChatModel":
        return False

    _, _, total_tokens = _extract_tokens(run)
    if total_tokens <= 0:
        return False

    scn = _extract_scenario(run)
    if scn is None:
        return False

    return True


def _extract_model_name(run: Any) -> str:
    """Extracts and normalizes the target LLM identifier from a LangSmith run."""
    extra = getattr(run, "extra", None) or {}
    metadata = getattr(run, "metadata", None) or (extra.get("metadata", {}) if isinstance(extra, dict) else {})
    tags = getattr(run, "tags", None) or []
    run_name = str(getattr(run, "name", "") or "").strip()

    # 1. extra.metadata.ls_model_name or run.metadata keys
    if isinstance(metadata, dict):
        for key in ["ls_model_name", "model_name", "model"]:
            if metadata.get(key):
                val = str(metadata[key]).strip()
                if val:
                    return "llama3:latest" if val == "llama3" else val

    # 2. extra.ls_model_name
    if isinstance(extra, dict) and extra.get("ls_model_name"):
        val = str(extra["ls_model_name"]).strip()
        if val:
            return "llama3:latest" if val == "llama3" else val

    # 3. extra.invocation_params
    if isinstance(extra, dict):
        inv_params = extra.get("invocation_params")
        if isinstance(inv_params, dict):
            for k in ["model_name", "model"]:
                if inv_params.get(k):
                    val = str(inv_params[k]).strip()
                    if val:
                        return "llama3:latest" if val == "llama3" else val

    # 4. Known model identifiers matching tags or run name
    known_model_substrings = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "llama3:latest",
        "llama3",
    ]
    for km in known_model_substrings:
        if km in run_name:
            return "llama3:latest" if km == "llama3" else km

    if isinstance(tags, list):
        for tag in tags:
            tag_str = str(tag).strip()
            for km in known_model_substrings:
                if km in tag_str:
                    return "llama3:latest" if km == "llama3" else km
            if tag_str.startswith("model:"):
                raw_m = tag_str.split("model:", 1)[1].strip()
                return "llama3:latest" if raw_m == "llama3" else raw_m

    if run_name and run_name not in ["ChatGroq", "ChatOllama", "OfflineFallbackChatModel"]:
        return run_name

    return "default-llm"


def _extract_duration_ms(run: Any) -> float:
    """Calculates duration in milliseconds from run latency or timestamps."""
    latency = getattr(run, "latency", None)
    if latency is not None:
        try:
            return max(0.0, float(latency) * 1000.0)
        except (ValueError, TypeError):
            pass

    end_time = getattr(run, "end_time", None)
    start_time = getattr(run, "start_time", None)
    if end_time and start_time:
        try:
            delta = (end_time - start_time).total_seconds() * 1000.0
            return max(0.0, delta)
        except Exception:
            pass

    return 0.0


def _extract_tokens(run: Any) -> tuple[int, int, int]:
    """Extracts prompt, completion, and total tokens from run properties or extra usage dict."""
    prompt = getattr(run, "prompt_tokens", None)
    completion = getattr(run, "completion_tokens", None)
    total = getattr(run, "total_tokens", None)

    extra = getattr(run, "extra", None) or {}
    token_usage = extra.get("token_usage", {}) if isinstance(extra, dict) else {}

    if prompt is None and isinstance(token_usage, dict):
        prompt = token_usage.get("prompt_tokens")
    if completion is None and isinstance(token_usage, dict):
        completion = token_usage.get("completion_tokens")
    if total is None and isinstance(token_usage, dict):
        total = token_usage.get("total_tokens")

    p = int(prompt) if prompt is not None else 0
    c = int(completion) if completion is not None else 0
    t = int(total) if total is not None else (p + c)

    return max(0, p), max(0, c), max(0, t)


def _extract_cost(run: Any) -> float:
    """Extracts total cost in USD, defaulting to 0.0 for local/unpriced runs."""
    cost = getattr(run, "total_cost", None)
    if cost is not None:
        try:
            return max(0.0, float(cost))
        except (ValueError, TypeError):
            pass

    extra = getattr(run, "extra", None) or {}
    if isinstance(extra, dict) and "total_cost" in extra:
        try:
            return max(0.0, float(extra["total_cost"]))
        except (ValueError, TypeError):
            pass

    return 0.0


def _is_run_successful(run: Any) -> bool:
    """Evaluates whether the run concluded with a success status without uncaught errors."""
    status = getattr(run, "status", None)
    error = getattr(run, "error", None)

    if status is not None and str(status).lower() in {"success", "completed"}:
        return True
    if error is not None and str(error).strip():
        return False
    if status is not None and str(status).lower() == "error":
        return False
    return True


def _compute_group_metric(model_name: str, scenario: str, group: list[Any]) -> ModelScenarioMetric:
    """Computes statistical aggregations for a grouped (model, scenario) list of runs."""
    runs_count = len(group)
    durations = [_extract_duration_ms(r) for r in group]
    prompt_tokens = [p for p, _, _ in [_extract_tokens(r) for r in group]]
    completion_tokens = [c for _, c, _ in [_extract_tokens(r) for r in group]]
    total_tokens = [t for _, _, t in [_extract_tokens(r) for r in group]]
    costs = [_extract_cost(r) for r in group]
    success_count = sum(1 for r in group if _is_run_successful(r))

    mean_duration_ms = round(statistics.mean(durations), 2) if durations else 0.0
    median_duration_ms = round(statistics.median(durations), 2) if durations else 0.0

    if not durations:
        p95_duration_ms = 0.0
    elif len(durations) == 1:
        p95_duration_ms = round(durations[0], 2)
    else:
        sorted_d = sorted(durations)
        rank = 0.95 * (len(sorted_d) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_d) - 1)
        weight = rank - lower
        p95_duration_ms = round(
            sorted_d[lower] * (1.0 - weight) + sorted_d[upper] * weight,
            2,
        )

    mean_prompt = round(statistics.mean(prompt_tokens), 1) if prompt_tokens else 0.0
    mean_compl = round(statistics.mean(completion_tokens), 1) if completion_tokens else 0.0
    mean_tot = round(statistics.mean(total_tokens), 1) if total_tokens else 0.0
    total_cost = round(sum(costs), 5)
    success_rate = round((success_count / runs_count) * 100.0, 1) if runs_count > 0 else 0.0

    return ModelScenarioMetric(
        model_name=model_name,
        scenario=scenario,
        runs_count=runs_count,
        mean_duration_ms=mean_duration_ms,
        median_duration_ms=median_duration_ms,
        p95_duration_ms=p95_duration_ms,
        mean_prompt_tokens=mean_prompt,
        mean_completion_tokens=mean_compl,
        mean_total_tokens=mean_tot,
        total_cost_usd=total_cost,
        success_rate_pct=success_rate,
    )


# ---------------------------------------------------------------------------
# Primary Extraction Entrypoint
# ---------------------------------------------------------------------------


def pull_langsmith_metrics(
    project_name: Optional[str] = None,
    client: Optional[Any] = None,
    filter_query: Optional[str] = None,
) -> LangSmithMetricsSuiteReport:
    """Extracts, filters, and aggregates multi-model runs from a LangSmith project.

    Args:
        project_name: Optional target project name (defaults to LANGSMITH_PROJECT env or 'REIC_WESAAC_code').
        client: Optional pre-configured LangSmith Client instance (used for testing/mocking).
        filter_query: Optional filter expression passed to LangSmith runs query.

    Returns:
        LangSmithMetricsSuiteReport: Immutable Pydantic v2 aggregated report.
    """
    report_id = f"ls-report-{uuid.uuid4().hex[:8]}"
    extracted_at = datetime.now(timezone.utc).isoformat()

    resolved_project = (
        project_name
        or os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or "REIC_WESAAC_code"
    ).strip()

    notes: list[str] = []

    try:
        if client is None:
            if LangSmithClient is None:
                return LangSmithMetricsSuiteReport(
                    report_id=report_id,
                    project_name=resolved_project,
                    extracted_at=extracted_at,
                    total_runs_analyzed=0,
                    metrics=[],
                    all_passed=False,
                    notes=["LangSmith SDK is not installed in the environment."],
                )
            api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
            if not api_key:
                return LangSmithMetricsSuiteReport(
                    report_id=report_id,
                    project_name=resolved_project,
                    extracted_at=extracted_at,
                    total_runs_analyzed=0,
                    metrics=[],
                    all_passed=False,
                    notes=["LANGSMITH_API_KEY environment variable is missing or empty."],
                )
            client = LangSmithClient(api_key=api_key)

        proj = client.read_project(project_name=resolved_project)
        project_id = getattr(proj, "id", None)
        if project_id is None and isinstance(proj, dict):
            project_id = proj.get("id")
        if project_id is None:
            project_id = resolved_project

        filter_expr = filter_query or 'and(eq(run_type, "llm"), gt(total_tokens, 0))'
        try:
            runs_iterable = client.list_runs(project_id=project_id, filter=filter_expr)
            raw_runs = list(runs_iterable)
        except TypeError:
            runs_iterable = client.list_runs(project_id=project_id, is_root=True, limit=100)
            raw_runs = list(runs_iterable)

        filtered_runs: list[Any] = []
        for r in raw_runs:
            if _is_sprint_mas_run(r):
                filtered_runs.append(r)

        if not filtered_runs:
            notes.append(f"No sprint-mas runs found in project '{resolved_project}'.")
            return LangSmithMetricsSuiteReport(
                report_id=report_id,
                project_name=resolved_project,
                extracted_at=extracted_at,
                total_runs_analyzed=0,
                metrics=[],
                all_passed=True,
                notes=notes,
            )

        groups: dict[tuple[str, str], list[Any]] = {}
        for r in filtered_runs:
            scn = _extract_scenario(r) or "unknown_scenario"
            model = _extract_model_name(r)
            groups.setdefault((model, scn), []).append(r)

        metrics: list[ModelScenarioMetric] = []
        for (model, scn), group in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])):
            metric = _compute_group_metric(model, scn, group)
            metrics.append(metric)

        notes.append(
            f"Successfully analyzed {len(filtered_runs)} runs across {len(metrics)} model/scenario combinations."
        )

        all_passed = all(m.success_rate_pct == 100.0 for m in metrics) if metrics else True

        return LangSmithMetricsSuiteReport(
            report_id=report_id,
            project_name=resolved_project,
            extracted_at=extracted_at,
            total_runs_analyzed=len(filtered_runs),
            metrics=metrics,
            all_passed=all_passed,
            notes=notes,
        )

    except (LangSmithRateLimitError, LangSmithAuthError, LangSmithError, Exception) as exc:
        notes.append(f"LangSmith API communication error: {exc}")
        return LangSmithMetricsSuiteReport(
            report_id=report_id,
            project_name=resolved_project,
            extracted_at=extracted_at,
            total_runs_analyzed=0,
            metrics=[],
            all_passed=False,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Formatters and Safe Artifact Exporters
# ---------------------------------------------------------------------------


def format_metrics_markdown(report: LangSmithMetricsSuiteReport) -> str:
    """Formats executive markdown report comparing multi-model performance metrics."""
    lines = [
        "# LangSmith Multi-Model Empirical Metrics Summary",
        "",
        f"- **Project:** `{report.project_name}`",
        f"- **Report ID:** `{report.report_id}`",
        f"- **Extracted At:** {report.extracted_at}",
        f"- **Total Runs Analyzed:** {report.total_runs_analyzed}",
        f"- **Status:** {'PASSED' if report.all_passed else 'FLAGGED / INCOMPLETE'}",
        "",
    ]

    if not report.metrics:
        lines.append("*No metrics available for this project.*")
    else:
        lines.append(
            "| Model | Scenario | Runs | Mean (ms) | Median (ms) | P95 (ms) | Prompt Tok. | Compl. Tok. | Total Tok. | Total Cost ($) | Success (%) |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for m in report.metrics:
            lines.append(
                f"| `{m.model_name}` | `{m.scenario}` | {m.runs_count} | "
                f"{m.mean_duration_ms:.2f} | {m.median_duration_ms:.2f} | {m.p95_duration_ms:.2f} | "
                f"{m.mean_prompt_tokens:.1f} | {m.mean_completion_tokens:.1f} | {m.mean_total_tokens:.1f} | "
                f"${m.total_cost_usd:.5f} | {m.success_rate_pct:.1f}% |"
            )

    if report.notes:
        lines.append("")
        lines.append("### Notes & Diagnostics")
        for note in report.notes:
            lines.append(f"- {note}")

    lines.append("")
    return "\n".join(lines)


def format_metrics_latex(report: LangSmithMetricsSuiteReport) -> str:
    """Generates camera-ready LaTeX booktabs table for academic papers (WESAAC/REIC)."""
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{LangSmith Multi-Model Empirical Benchmark Comparison (WESAAC/REIC)}",
        r"\label{tab:langsmith_metrics_comparison}",
        r"\begin{tabular}{llrrrrrrrr}",
        r"\toprule",
        r"\textbf{Model} & \textbf{Scenario} & \textbf{Runs} & \textbf{Mean (ms)} & \textbf{P95 (ms)} & \textbf{Prompt Tok.} & \textbf{Compl. Tok.} & \textbf{Total Tok.} & \textbf{Cost (\$)} & \textbf{Success (\%)} \\",
        r"\midrule",
    ]

    for m in report.metrics:
        m_name = m.model_name.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
        scn_name = m.scenario.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
        lines.append(
            f"{m_name} & {scn_name} & {m.runs_count} & {m.mean_duration_ms:.2f} & {m.p95_duration_ms:.2f} & "
            f"{m.mean_prompt_tokens:.1f} & {m.mean_completion_tokens:.1f} & {m.mean_total_tokens:.1f} & "
            f"{m.total_cost_usd:.5f} & {m.success_rate_pct:.1f}\\% \\\\"
        )

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ])
    return "\n".join(lines)


def format_metrics_csv(report: LangSmithMetricsSuiteReport) -> str:
    """Generates standard CSV representation using Unix newlines to prevent CRCRLF issues."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "model_name",
        "scenario",
        "runs_count",
        "mean_duration_ms",
        "median_duration_ms",
        "p95_duration_ms",
        "mean_prompt_tokens",
        "mean_completion_tokens",
        "mean_total_tokens",
        "total_cost_usd",
        "success_rate_pct",
    ])
    for m in report.metrics:
        writer.writerow([
            m.model_name,
            m.scenario,
            m.runs_count,
            f"{m.mean_duration_ms:.2f}",
            f"{m.median_duration_ms:.2f}",
            f"{m.p95_duration_ms:.2f}",
            f"{m.mean_prompt_tokens:.1f}",
            f"{m.mean_completion_tokens:.1f}",
            f"{m.mean_total_tokens:.1f}",
            f"{m.total_cost_usd:.5f}",
            f"{m.success_rate_pct:.1f}",
        ])
    return output.getvalue()


def export_metrics_artifacts(
    report: LangSmithMetricsSuiteReport,
    base_filename: str = "langsmith_metrics_summary",
    output_dir: Optional[Union[str, Path]] = None,
) -> dict[str, Path]:
    """Safely exports benchmark metrics artifacts in .json, .md, .csv, and .tex formats.

    Args:
        report: Aggregated LangSmithMetricsSuiteReport.
        base_filename: Target base filename without extension.
        output_dir: Optional output directory (defaults to reports/experiments/).

    Returns:
        dict[str, Path]: Dictionary mapping format identifiers ('json', 'md', 'csv', 'tex') to written paths.
    """
    repo_root = Path(__file__).resolve().parent.parent.resolve()
    base_dir = repo_root
    if output_dir:
        out_dir_path = Path(output_dir)
        if not out_dir_path.is_absolute():
            out_dir_path = (repo_root / out_dir_path).resolve()
        else:
            out_dir_path = out_dir_path.resolve()
            try:
                if not out_dir_path.is_relative_to(repo_root):
                    base_dir = out_dir_path
            except AttributeError:
                if not str(out_dir_path).startswith(str(repo_root)):
                    base_dir = out_dir_path
    else:
        out_dir_path = (repo_root / "reports" / "experiments").resolve()

    clean_base = base_filename
    for sfx in [".json", ".md", ".csv", ".tex"]:
        if clean_base.lower().endswith(sfx):
            clean_base = clean_base[:-len(sfx)]

    target_json = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.json", base_dir=base_dir)
    target_md = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.md", base_dir=base_dir)
    target_csv = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.csv", base_dir=base_dir)
    target_tex = validate_safe_benchmark_path(out_dir_path / f"{clean_base}.tex", base_dir=base_dir)

    out_dir_path.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, Path] = {}

    target_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    artifacts["json"] = target_json

    target_md.write_text(format_metrics_markdown(report), encoding="utf-8")
    artifacts["md"] = target_md

    target_csv.write_text(format_metrics_csv(report), encoding="utf-8", newline="")
    artifacts["csv"] = target_csv

    target_tex.write_text(format_metrics_latex(report), encoding="utf-8")
    artifacts["tex"] = target_tex

    return artifacts


export_langsmith_metrics_artifacts = export_metrics_artifacts
