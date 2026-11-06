"""Comprehensive test suite for Phase 10: Empirical Evaluation & Human Comparative (sprint_mas/evaluation.py & main.py)."""

import concurrent.futures
import csv
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from sprint_mas.benchmarks import (
    BenchmarkConfig,
    BenchmarkSuiteReport,
    run_benchmark_suite,
    validate_safe_benchmark_path,
)
from sprint_mas.data_loader import load_scenario
from sprint_mas.evaluation import (
    BottleneckMitigationAnalysis,
    EmpiricalEvaluationReport,
    PaperBaselineMetrics,
    ScenarioEmpiricalComparison,
    analyze_resource_bottleneck_mitigation,
    compute_speedup_metrics,
    export_empirical_evaluation,
    format_empirical_evaluation_csv,
    format_empirical_evaluation_latex,
    format_empirical_evaluation_markdown,
    get_paper_baselines,
    run_empirical_evaluation,
)
from sprint_mas.state import Allocation, DeveloperProfile, Task
from main import run_cli


# ============================================================================
# 1. Contract Validation & Canonical Baselines (REIC 2026 / WESAAC 2025)
# ============================================================================


def test_get_paper_baselines_canonical_figures() -> None:
    """When get_paper_baselines is called, it returns the exact immutable paper figures for A, B, and C."""
    baselines = get_paper_baselines()
    assert set(baselines.keys()) == {"scenario_a", "scenario_b", "scenario_c"}

    # Scenario A
    base_a = baselines["scenario_a"]
    assert base_a.scenario == "scenario_a"
    assert base_a.manual_time_ms is None
    assert base_a.manual_error_rate_pct == 0.0
    assert base_a.manual_cognitive_fatigue == "LOW"
    assert base_a.n8n_success_rate_pct == 100.0

    # Scenario B (Canonical benchmark from REIC 2026 Seções 5.2, 6, 6.1, 6.2, 6.3)
    base_b = baselines["scenario_b"]
    assert base_b.scenario == "scenario_b"
    assert base_b.manual_time_ms == 765000.0  # 12m 45s = 765.0s
    assert base_b.manual_error_rate_pct == 0.0
    assert base_b.manual_cognitive_fatigue == "HIGH_FATIGUE"
    assert base_b.n8n_agent_time_ms == 4200.0  # 4.2s
    assert base_b.n8n_agent_speedup_vs_manual == 182.14
    assert base_b.n8n_success_rate_pct == 100.0
    assert "REIC 2026" in base_b.source_citation

    # Scenario C (Scale stress: 100 tasks, n8n timeout rate of 0.5%)
    base_c = baselines["scenario_c"]
    assert base_c.scenario == "scenario_c"
    assert base_c.manual_time_ms is None
    assert base_c.manual_cognitive_fatigue == "INFEASIBLE"
    assert base_c.n8n_success_rate_pct == 99.5


def test_paper_baseline_metrics_forbids_extra_fields() -> None:
    """PaperBaselineMetrics forbids unauthorized injected fields."""
    with pytest.raises(ValidationError):
        PaperBaselineMetrics(
            scenario="scenario_b",
            manual_cognitive_fatigue="HIGH_FATIGUE",
            n8n_success_rate_pct=100.0,
            unauthorized_field="malicious",  # type: ignore[call-arg]
        )


def test_bottleneck_mitigation_analysis_forbids_extra_fields() -> None:
    """BottleneckMitigationAnalysis forbids extra fields via ConfigDict(extra='forbid')."""
    with pytest.raises(ValidationError):
        BottleneckMitigationAnalysis(
            scenario="scenario_b",
            total_tasks=30,
            backend_tasks_count=19,
            backend_density_pct=63.33,
            dev_c_allocated_tasks=5,
            dev_c_backend_tasks_absorbed=4,
            dev_c_backend_points_absorbed=18,
            dev_d_allocated_points=10.0,
            dev_d_capacity_ceiling=10.0,
            dev_d_capacity_respected=True,
            fullstack_mitigation_active=True,
            summary="Test",
            injected_field="extra",  # type: ignore[call-arg]
        )


def test_scenario_empirical_comparison_forbids_extra_fields() -> None:
    """ScenarioEmpiricalComparison forbids extra fields via ConfigDict(extra='forbid')."""
    with pytest.raises(ValidationError):
        ScenarioEmpiricalComparison(
            scenario="scenario_b",
            langgraph_time_ms=1500.0,
            manual_feasibility="HIGH_FATIGUE",
            n8n_success_rate_pct=100.0,
            unknown_arg=123,  # type: ignore[call-arg]
        )


def test_empirical_evaluation_report_forbids_extra_fields() -> None:
    """EmpiricalEvaluationReport forbids extra fields via ConfigDict(extra='forbid')."""
    with pytest.raises(ValidationError):
        EmpiricalEvaluationReport(
            report_id="rep-1",
            timestamp="2026-11-05T00:00:00Z",
            provider="offline",
            model="offline_fallback",
            comparisons=[],
            extra_payload="malicious",  # type: ignore[call-arg]
        )


# ============================================================================
# 2. Mathematical Speedup & Efficiency Metrics
# ============================================================================


def test_compute_speedup_metrics_canonical_values() -> None:
    """When manual_time_ms=765000.0 and agent_time_ms=4200.0, computes 182.14x speedup and 99.45% time reduction."""
    speedup, reduction = compute_speedup_metrics(manual_time_ms=765000.0, agent_time_ms=4200.0)
    assert speedup == 182.14
    assert reduction == 99.45


def test_compute_speedup_metrics_instantaneous_agent_safe_floor() -> None:
    """When agent_time_ms is 0.0 (instantaneous mock), it applies safe floor of 0.001 ms avoiding ZeroDivisionError."""
    speedup, reduction = compute_speedup_metrics(manual_time_ms=765000.0, agent_time_ms=0.0)
    assert speedup == 765000000.0
    assert reduction == 100.0


@pytest.mark.parametrize(
    ("manual_ms", "agent_ms"),
    [
        (0.0, 100.0),
        (-100.0, 100.0),
        (500.0, -10.0),
        (-1.0, -1.0),
    ],
)
def test_compute_speedup_metrics_invalid_inputs_raise_value_error(
    manual_ms: float,
    agent_ms: float,
) -> None:
    """When invalid or negative times are supplied, compute_speedup_metrics raises ValueError."""
    with pytest.raises(ValueError):
        compute_speedup_metrics(manual_time_ms=manual_ms, agent_time_ms=agent_ms)


# ============================================================================
# 3. Qualitative Resource Bottleneck Mitigation (REIC 2026, Section 6.3)
# ============================================================================


def test_analyze_resource_bottleneck_mitigation_scenario_b_exact() -> None:
    """When analyze_resource_bottleneck_mitigation evaluates Scenario B, it proves 63.33% backend density, dev_C absorption, and dev_D capacity ceiling."""
    tasks, team = load_scenario("scenario_b")

    # Synthetic realistic allocations for Scenario B
    allocations = [
        # dev_B (Backend specialist, 0.7 FTE = 14 pts ceiling): 14 pts
        Allocation(task_id="TSK-101", developer_id="dev_B", reason="core backend", allocated_points=5),
        Allocation(task_id="TSK-102", developer_id="dev_B", reason="core backend", allocated_points=5),
        Allocation(task_id="TSK-109", developer_id="dev_B", reason="backend email", allocated_points=3),
        # dev_C (Fullstack, 1.0 FTE = 20 pts ceiling): absorbs backend tasks TSK-103 (8 pts) and TSK-104 (8 pts)
        Allocation(task_id="TSK-103", developer_id="dev_C", reason="absorbed backend bottleneck", allocated_points=8),
        Allocation(task_id="TSK-104", developer_id="dev_C", reason="absorbed backend bottleneck", allocated_points=8),
        # dev_D (Backend specialist, 0.5 FTE = 10 pts ceiling): strictly 10 pts
        Allocation(task_id="TSK-107", developer_id="dev_D", reason="gateway adapter", allocated_points=5),
        Allocation(task_id="TSK-108", developer_id="dev_D", reason="antifraud backend", allocated_points=5),
        # dev_A & dev_E: frontend tasks
        Allocation(task_id="TSK-106", developer_id="dev_A", reason="checkout UI", allocated_points=5),
        Allocation(task_id="TSK-111", developer_id="dev_E", reason="orders UI", allocated_points=3),
    ]

    analysis = analyze_resource_bottleneck_mitigation(
        backlog=tasks,
        team=team,
        allocations=allocations,
    )

    assert analysis.scenario == "scenario_b"
    assert analysis.total_tasks == 30
    assert analysis.backend_tasks_count == 19
    assert analysis.backend_density_pct == 63.33
    assert analysis.dev_c_allocated_tasks == 2
    assert analysis.dev_c_backend_tasks_absorbed == 2
    assert analysis.dev_c_backend_points_absorbed == 16
    assert analysis.dev_d_allocated_points == 10.0
    assert analysis.dev_d_capacity_ceiling == 10.0
    assert analysis.dev_d_capacity_respected is True
    assert analysis.fullstack_mitigation_active is True
    assert "63.33%" in analysis.summary
    assert "dev_C" in analysis.summary
    assert "dev_D" in analysis.summary


def test_analyze_resource_bottleneck_mitigation_dev_d_overload_flagged() -> None:
    """When dev_D receives more than 10.0 points, dev_d_capacity_respected is False."""
    tasks, team = load_scenario("scenario_b")

    overloaded_allocations = [
        Allocation(task_id="TSK-103", developer_id="dev_D", reason="overload", allocated_points=8),
        Allocation(task_id="TSK-104", developer_id="dev_D", reason="overload", allocated_points=8),
    ]

    analysis = analyze_resource_bottleneck_mitigation(
        backlog=tasks,
        team=team,
        allocations=overloaded_allocations,
    )

    assert analysis.dev_d_allocated_points == 16.0
    assert analysis.dev_d_capacity_ceiling == 10.0
    assert analysis.dev_d_capacity_respected is False


def test_analyze_resource_bottleneck_mitigation_empty_backlog_raises_error() -> None:
    """When backlog or team is empty, analyze_resource_bottleneck_mitigation raises ValueError."""
    tasks, team = load_scenario("scenario_b")
    with pytest.raises(ValueError):
        analyze_resource_bottleneck_mitigation(backlog=[], team=team, allocations=[])
    with pytest.raises(ValueError):
        analyze_resource_bottleneck_mitigation(backlog=tasks, team=[], allocations=[])


# ============================================================================
# 4. End-to-End Scientific Evaluation Pipeline
# ============================================================================


def test_run_empirical_evaluation_with_offline_mock() -> None:
    """When run_empirical_evaluation runs offline over Scenarios A and B, it produces complete EmpiricalEvaluationReport."""
    cfg = BenchmarkConfig(scenarios=["scenario_a", "scenario_b"], runs=1, offline_mock=True)
    report = run_empirical_evaluation(config=cfg)

    assert isinstance(report, EmpiricalEvaluationReport)
    assert report.report_id.startswith("empirical-eval-")
    assert len(report.comparisons) == 2

    comp_a = next(c for c in report.comparisons if c.scenario == "scenario_a")
    assert comp_a.manual_time_ms is None
    assert comp_a.speedup_vs_manual is None
    assert comp_a.langgraph_success_rate_pct == 100.0
    assert comp_a.manual_feasibility == "LOW"

    comp_b = next(c for c in report.comparisons if c.scenario == "scenario_b")
    assert comp_b.manual_time_ms == 765000.0
    assert comp_b.n8n_agent_time_ms == 4200.0
    assert comp_b.speedup_vs_manual is not None and comp_b.speedup_vs_manual > 0.0
    assert comp_b.time_reduction_vs_manual_pct is not None and comp_b.time_reduction_vs_manual_pct > 90.0
    assert comp_b.bottleneck_analysis is not None
    assert comp_b.bottleneck_analysis.backend_density_pct == 63.33
    assert comp_b.bottleneck_analysis.dev_d_capacity_respected is True

    assert report.total_speedup_scenario_b == comp_b.speedup_vs_manual


def test_run_empirical_evaluation_with_existing_suite_report() -> None:
    """When pre-computed BenchmarkSuiteReport is passed, run_empirical_evaluation reuses it without re-running benchmark suite."""
    cfg = BenchmarkConfig(scenarios=["scenario_b"], runs=1, offline_mock=True)
    suite_report = run_benchmark_suite(config=cfg)

    report = run_empirical_evaluation(suite_report=suite_report)
    assert len(report.comparisons) == 1
    assert report.comparisons[0].scenario == "scenario_b"
    assert report.comparisons[0].bottleneck_analysis is not None


# ============================================================================
# 5. Formatters: Markdown, CSV, and LaTeX Publication Tables
# ============================================================================


def test_format_empirical_evaluation_markdown() -> None:
    """format_empirical_evaluation_markdown generates detailed markdown report with Section 5, 6, and 6.3 tables."""
    cfg = BenchmarkConfig(scenarios=["scenario_b"], runs=1, offline_mock=True)
    report = run_empirical_evaluation(config=cfg)

    md = format_empirical_evaluation_markdown(report)
    assert "# Relatório de Avaliação Empírica & Comparativo Humano" in md
    assert "REIC 2026" in md
    assert "765,000" in md or "765000" in md
    assert "4,200" in md or "4200" in md
    assert "63.33%" in md
    assert "dev_C" in md
    assert "dev_D" in md
    assert "\\begin{table}" in md
    assert "\\end{table}" in md


def test_format_empirical_evaluation_csv() -> None:
    """format_empirical_evaluation_csv generates parseable CSV with canonical headers and metrics."""
    cfg = BenchmarkConfig(scenarios=["scenario_b"], runs=1, offline_mock=True)
    report = run_empirical_evaluation(config=cfg)

    csv_text = format_empirical_evaluation_csv(report)
    reader = list(csv.reader(csv_text.strip().splitlines()))
    headers = reader[0]

    assert "scenario" in headers
    assert "speedup_vs_manual" in headers
    assert "time_reduction_vs_manual_pct" in headers
    assert "langgraph_time_ms" in headers
    assert "dev_c_backend_absorbed_pts" in headers

    row = reader[1]
    assert row[0] == "scenario_b"


def test_format_empirical_evaluation_latex() -> None:
    """format_empirical_evaluation_latex generates valid LaTeX booktabs table ready for evaluation.tex."""
    cfg = BenchmarkConfig(scenarios=["scenario_a", "scenario_b", "scenario_c"], runs=1, offline_mock=True)
    report = run_empirical_evaluation(config=cfg)

    tex = format_empirical_evaluation_latex(report)
    assert "\\begin{table}" in tex
    assert "\\toprule" in tex
    assert "\\midrule" in tex
    assert "\\bottomrule" in tex
    assert "\\end{table}" in tex
    assert "Scenario\\_B" in tex or "scenario_b" in tex or "Scenario B" in tex
    assert "182.14" in tex or "LangGraph" in tex


# ============================================================================
# 6. Safe Artifact Export & Anti-Path Traversal (Pentagon of Security)
# ============================================================================


def test_validate_safe_benchmark_path_supports_tex() -> None:
    """validate_safe_benchmark_path allows .tex extension alongside .json, .md, .csv."""
    p = validate_safe_benchmark_path("reports/experiments/test_table.tex")
    assert p.suffix.lower() == ".tex"


def test_export_empirical_evaluation_artifacts_all_formats() -> None:
    """export_empirical_evaluation writes .json, .md, .csv, and .tex artifacts safely."""
    cfg = BenchmarkConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    report = run_empirical_evaluation(config=cfg)

    base_name = "test_eval_export_p10"
    out_dir = Path("reports/experiments/eval_p10_tmp")

    try:
        exported = export_empirical_evaluation(
            report=report,
            base_filename=base_name,
            output_dir=out_dir,
            export_json=True,
            export_md=True,
            export_csv=True,
            export_tex=True,
        )

        assert set(exported.keys()) == {"json", "md", "csv", "tex"}
        for k, path_obj in exported.items():
            assert path_obj.is_file(), f"Expected artifact {k} at {path_obj} to exist."
            assert path_obj.stat().st_size > 0

        # Anti-CRCRLF line-ending defensive assertion
        raw_csv_bytes = exported["csv"].read_bytes()
        assert b"\r\r\n" not in raw_csv_bytes, "CSV artifact contains duplicate carriage return b'\\r\\r\\n'!"
        with open(exported["csv"], "r", encoding="utf-8", newline="") as f:
            reader = list(csv.reader(f))
            assert len(reader) >= 2
            expected_cols = len(reader[0])
            for idx, row in enumerate(reader):
                assert len(row) == expected_cols, f"Row {idx+1} has {len(row)} columns, expected {expected_cols}"
    finally:
        if out_dir.exists():
            for child in out_dir.iterdir():
                child.unlink()
            out_dir.rmdir()


@pytest.mark.parametrize(
    "forbidden_path",
    [
        "../../evil.tex",
        "../outside.md",
        "reports/malicious.py",
        "reports/executable.exe",
        "",
    ],
)
def test_export_empirical_evaluation_blocks_unsafe_paths(forbidden_path: str) -> None:
    """export_empirical_evaluation blocks path traversal and disallowed extensions with ValueError."""
    cfg = BenchmarkConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    report = run_empirical_evaluation(config=cfg)

    with pytest.raises(ValueError):
        export_empirical_evaluation(
            report=report,
            base_filename="evil",
            output_dir=forbidden_path,
        )


# ============================================================================
# 7. Concurrency & State Isolation
# ============================================================================


def test_concurrent_empirical_evaluations() -> None:
    """When 5 empirical evaluations run in parallel with ThreadPoolExecutor, each produces isolated report without state corruption."""
    cfg = BenchmarkConfig(scenarios=["scenario_a", "scenario_b"], runs=1, offline_mock=True)

    def _worker(worker_idx: int) -> EmpiricalEvaluationReport:
        return run_empirical_evaluation(config=cfg)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_worker, i) for i in range(5)]
        results = [f.result() for f in futures]

    assert len(results) == 5
    report_ids = [r.report_id for r in results]
    assert len(set(report_ids)) == 5  # Each report has a unique report_id


# ============================================================================
# 8. Executive CLI Integration (main.py --evaluate-human)
# ============================================================================


def test_cli_evaluate_human_flag_happy_path(capsys: pytest.CaptureFixture[str]) -> None:
    """When CLI runs --evaluate-human with offline mock, it displays empirical evaluation report and exits 0."""
    exit_code = run_cli(["--evaluate-human", "--offline-mock", "-s", "scenario_b", "--runs", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Avaliação Empírica" in captured.out or "Empirical Evaluation" in captured.out
    assert "scenario_b" in captured.out
    assert "Speedup" in captured.out or "speedup" in captured.out.lower()


def test_cli_evaluate_human_short_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """When CLI runs -e with offline mock, it displays empirical evaluation report and exits 0."""
    exit_code = run_cli(["-e", "--offline-mock", "-s", "scenario_a", "--runs", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "scenario_a" in captured.out


def test_cli_evaluate_human_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """When CLI runs --evaluate-human --json, it prints valid JSON matching EmpiricalEvaluationReport schema."""
    exit_code = run_cli(["-e", "--json", "--offline-mock", "-s", "scenario_a", "--runs", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    assert "report_id" in data
    assert "comparisons" in data
    assert len(data["comparisons"]) == 1
    assert data["comparisons"][0]["scenario"] == "scenario_a"


def test_cli_evaluate_human_export_prefix() -> None:
    """When CLI runs -e with --export-prefix, it exports .json, .md, .csv, and .tex artifacts."""
    prefix = "reports/experiments/test_cli_eval_p10_prefix"
    repo_root = Path(__file__).resolve().parent.parent

    try:
        exit_code = run_cli(
            [
                "-e",
                "--offline-mock",
                "-s",
                "scenario_a",
                "--runs",
                "1",
                "--export-prefix",
                prefix,
            ]
        )
        assert exit_code == 0

        for ext in [".json", ".md", ".csv", ".tex"]:
            target_path = repo_root / f"{prefix}{ext}"
            assert target_path.is_file(), f"Expected CLI exported artifact {target_path} to exist."
    finally:
        for ext in [".json", ".md", ".csv", ".tex"]:
            target_path = repo_root / f"{prefix}{ext}"
            if target_path.exists():
                target_path.unlink()


def test_cli_evaluate_human_circuit_breaker_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    """When scope trimming is disabled on Scenario B, circuit breaker trips and CLI returns exit code 2."""
    exit_code = run_cli(
        [
            "-e",
            "--offline-mock",
            "-s",
            "scenario_b",
            "--no-trim",
            "--max-retries",
            "1",
            "--runs",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "scenario_b" in captured.out


def test_cli_evaluate_human_path_traversal_returns_exit_code_1() -> None:
    """When CLI receives an unsafe path traversal in --output, it returns exit code 1."""
    exit_code = run_cli(["-e", "--offline-mock", "--output", "../../evil.tex"])
    assert exit_code == 1


def test_cli_evaluate_human_invalid_runs_returns_exit_code_1() -> None:
    """When CLI receives invalid runs (0 or >50), it returns exit code 1."""
    exit_code = run_cli(["-e", "--offline-mock", "--runs", "0"])
    assert exit_code == 1
