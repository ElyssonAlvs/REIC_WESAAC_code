"""Comprehensive test suite for Phase 9: Live Execution & Benchmarks Automatizados."""

import concurrent.futures
import csv
import io
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from sprint_mas.benchmarks import (
    BenchmarkConfig,
    BenchmarkSuiteReport,
    ScenarioBenchmarkSummary,
    ScenarioRunMetric,
    export_benchmark_artifacts,
    format_benchmark_csv,
    format_benchmark_markdown,
    run_benchmark_suite,
    run_scenario_benchmark,
    validate_safe_benchmark_path,
)
from main import run_cli


# ============================================================================
# 1. Contract Validation (Pydantic v2 & Extra Forbid)
# ============================================================================


def test_benchmark_config_defaults_and_normalization() -> None:
    """BenchmarkConfig has default scenarios (a, b, c), runs=1, and normalizes scenario aliases."""
    cfg = BenchmarkConfig()
    assert cfg.scenarios == ["scenario_a", "scenario_b", "scenario_c"]
    assert cfg.runs == 1
    assert cfg.offline_mock is False
    assert cfg.sprint_days == 10
    assert cfg.points_per_day == 2.0
    assert cfg.enable_scope_trimming is True
    assert cfg.strict is False

    custom = BenchmarkConfig(scenarios=["a", "scenario_b"], runs=3, offline_mock=True)
    assert custom.scenarios == ["scenario_a", "scenario_b"]
    assert custom.runs == 3
    assert custom.offline_mock is True


def test_benchmark_config_forbids_extra_fields() -> None:
    """BenchmarkConfig rejects unauthorized injected fields with ValidationError."""
    with pytest.raises(ValidationError):
        BenchmarkConfig(unauthorized_injected_field="malicious")  # type: ignore[call-arg]


@pytest.mark.parametrize("invalid_runs", [0, -1, 51, 100])
def test_benchmark_config_runs_bounds(invalid_runs: int) -> None:
    """BenchmarkConfig enforces 1 <= runs <= 50."""
    with pytest.raises(ValidationError):
        BenchmarkConfig(runs=invalid_runs)


def test_benchmark_config_empty_scenarios_rejected() -> None:
    """BenchmarkConfig rejects empty scenario list."""
    with pytest.raises(ValidationError):
        BenchmarkConfig(scenarios=[])


def test_benchmark_config_unknown_scenario_rejected() -> None:
    """BenchmarkConfig rejects non-existent scenario names."""
    with pytest.raises(ValidationError):
        BenchmarkConfig(scenarios=["unknown_scenario_xyz"])


def test_metric_and_report_models_forbid_extra_fields() -> None:
    """All benchmark telemetry and report models enforce extra='forbid'."""
    with pytest.raises(ValidationError):
        ScenarioRunMetric(
            run_index=1,
            scenario="scenario_a",
            thread_id="t-1",
            execution_time_ms=10.0,
            approved=True,
            total_tasks=10,
            allocated_tasks=10,
            total_points=35,
            allocated_points=35,
            team_capacity=74.0,
            utilization_pct=47.3,
            validation_attempts=1,
            replan_triggered=False,
            dag_violations=0,
            fte_violations=0,
            skill_violations=0,
            llm_fallback_triggered=True,
            nodes_traversed=["prioritizer"],
            injected_field="bad",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ScenarioBenchmarkSummary(
            scenario="scenario_a",
            total_runs=1,
            successful_runs=1,
            approval_rate=1.0,
            mean_time_ms=10.0,
            std_time_ms=0.0,
            median_time_ms=10.0,
            min_time_ms=10.0,
            max_time_ms=10.0,
            p95_time_ms=10.0,
            mean_allocated_points=35.0,
            mean_utilization_pct=47.3,
            replan_rate=0.0,
            dag_violations_total=0,
            fte_violations_total=0,
            skill_violations_total=0,
            runs_metrics=[],
            injected_extra=123,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        BenchmarkSuiteReport(
            suite_id="s-1",
            timestamp="2026-11-04T00:00:00Z",
            config=BenchmarkConfig(),
            provider="offline",
            model="deterministic-fallback",
            summaries=[],
            total_execution_time_ms=100.0,
            all_approved=True,
            injected_admin=True,  # type: ignore[call-arg]
        )


# ============================================================================
# 2. Statistical Metrics & Edge Cases
# ============================================================================


def test_scenario_benchmark_runs_equal_one_std_is_zero() -> None:
    """When runs=1, standard deviation std_time_ms must be exactly 0.0 without StatisticsError."""
    summary = run_scenario_benchmark(
        "scenario_a",
        config=BenchmarkConfig(scenarios=["scenario_a"], runs=1, offline_mock=True),
    )
    assert summary.total_runs == 1
    assert summary.std_time_ms == 0.0
    assert summary.mean_time_ms > 0.0
    assert summary.median_time_ms == summary.mean_time_ms
    assert summary.min_time_ms == summary.mean_time_ms
    assert summary.max_time_ms == summary.mean_time_ms
    assert summary.p95_time_ms == summary.mean_time_ms


def test_scenario_benchmark_multiple_runs_statistics() -> None:
    """When runs=3, mean, median, min, max, std, and p95 are mathematically consistent."""
    summary = run_scenario_benchmark(
        "scenario_a",
        config=BenchmarkConfig(scenarios=["scenario_a"], runs=3, offline_mock=True),
    )
    assert summary.total_runs == 3
    assert summary.successful_runs == 3
    assert summary.approval_rate == 1.0
    assert summary.min_time_ms <= summary.median_time_ms <= summary.max_time_ms
    assert summary.std_time_ms >= 0.0
    assert len(summary.runs_metrics) == 3


# ============================================================================
# 3. Deterministic Scenarios A, B, and C Execution
# ============================================================================


def test_run_scenario_benchmark_scenario_a() -> None:
    """Scenario A benchmark produces 35 allocated points, 10 tasks, 0 violations, and 1 attempt."""
    summary = run_scenario_benchmark(
        "a",
        config=BenchmarkConfig(scenarios=["a"], runs=1, offline_mock=True),
    )
    assert summary.scenario == "scenario_a"
    assert summary.approval_rate == 1.0
    assert summary.mean_allocated_points == 35.0
    assert summary.replan_rate == 0.0
    assert summary.dag_violations_total == 0
    assert summary.fte_violations_total == 0
    assert summary.skill_violations_total == 0

    metric = summary.runs_metrics[0]
    assert metric.total_tasks == 10
    assert metric.allocated_tasks == 10
    assert metric.total_points == 35
    assert metric.allocated_points == 35
    assert metric.validation_attempts == 1
    assert metric.replan_triggered is False
    assert metric.approved is True


def test_run_scenario_benchmark_scenario_b() -> None:
    """Scenario B benchmark produces 66 allocated points, 15 tasks, replan triggered, 0 violations."""
    summary = run_scenario_benchmark(
        "b",
        config=BenchmarkConfig(scenarios=["b"], runs=1, offline_mock=True),
    )
    assert summary.scenario == "scenario_b"
    assert summary.approval_rate == 1.0
    assert summary.mean_allocated_points == 66.0
    assert summary.replan_rate == 1.0
    assert summary.dag_violations_total == 0
    assert summary.fte_violations_total == 0
    assert summary.skill_violations_total == 0

    metric = summary.runs_metrics[0]
    assert metric.total_tasks == 30
    assert metric.allocated_tasks == 15
    assert metric.total_points == 128
    assert metric.allocated_points == 66
    assert metric.validation_attempts == 2
    assert metric.replan_triggered is True
    assert metric.approved is True


def test_run_scenario_benchmark_scenario_c() -> None:
    """Scenario C benchmark produces 176 allocated points, 41 tasks, replan triggered, 0 violations."""
    summary = run_scenario_benchmark(
        "c",
        config=BenchmarkConfig(scenarios=["c"], runs=1, offline_mock=True),
    )
    assert summary.scenario == "scenario_c"
    assert summary.approval_rate == 1.0
    assert summary.mean_allocated_points == 176.0
    assert summary.replan_rate == 1.0
    assert summary.dag_violations_total == 0
    assert summary.fte_violations_total == 0
    assert summary.skill_violations_total == 0

    metric = summary.runs_metrics[0]
    assert metric.total_tasks == 100
    assert metric.allocated_tasks == 37
    assert metric.total_points == 452
    assert metric.allocated_points == 176
    assert metric.validation_attempts == 2
    assert metric.replan_triggered is True
    assert metric.approved is True


def test_run_scenario_benchmark_circuit_breaker_rejection() -> None:
    """When scope trimming is disabled on Scenario B, circuit breaker trips and summary records rejection."""
    summary = run_scenario_benchmark(
        "b",
        config=BenchmarkConfig(
            scenarios=["b"],
            runs=1,
            offline_mock=True,
            enable_scope_trimming=False,
            max_retries=1,
        ),
    )
    assert summary.scenario == "scenario_b"
    assert summary.approval_rate == 0.0
    assert summary.successful_runs == 0
    assert summary.fte_violations_total > 0
    metric = summary.runs_metrics[0]
    assert metric.approved is False
    assert metric.fte_violations > 0


def test_run_benchmark_suite_all_scenarios() -> None:
    """Suite execution consolidates scenarios A, B, and C with all_approved=True."""
    report = run_benchmark_suite(
        config=BenchmarkConfig(scenarios=["a", "b", "c"], runs=1, offline_mock=True)
    )
    assert isinstance(report, BenchmarkSuiteReport)
    assert report.suite_id.startswith("bench-")
    assert len(report.summaries) == 3
    assert report.all_approved is True
    assert report.total_execution_time_ms > 0.0

    sc_map = {s.scenario: s for s in report.summaries}
    assert "scenario_a" in sc_map
    assert "scenario_b" in sc_map
    assert "scenario_c" in sc_map
    assert sc_map["scenario_a"].mean_allocated_points == 35.0
    assert sc_map["scenario_b"].mean_allocated_points == 66.0
    assert sc_map["scenario_c"].mean_allocated_points == 176.0


# ============================================================================
# 4. Artifact Formatters (Markdown and CSV)
# ============================================================================


def test_format_benchmark_markdown() -> None:
    """Markdown formatter produces structured GitHub table matching required columns."""
    report = run_benchmark_suite(
        config=BenchmarkConfig(scenarios=["a", "b"], runs=1, offline_mock=True)
    )
    md = format_benchmark_markdown(report)

    assert "# Benchmark Suite Report" in md
    assert "Cenário" in md
    assert "Tarefas (Total/Alocadas)" in md
    assert "Pontos (Alocados/Capacidade)" in md
    assert "Utilização %" in md
    assert "Tentativas" in md
    assert "Replan?" in md
    assert "Violações (DAG/FTE/Skill)" in md
    assert "Tempo Médio (ms)" in md
    assert "P95 (ms)" in md
    assert "scenario_a" in md
    assert "scenario_b" in md
    assert "STATUS GERAL: APPROVED" in md


def test_format_benchmark_csv() -> None:
    """CSV formatter generates valid RFC 4180 CSV with all required metrics per run."""
    report = run_benchmark_suite(
        config=BenchmarkConfig(scenarios=["a", "b"], runs=1, offline_mock=True)
    )
    csv_text = format_benchmark_csv(report)

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 2
    assert "suite_id" in rows[0]
    assert "scenario" in rows[0]
    assert "run_index" in rows[0]
    assert "execution_time_ms" in rows[0]
    assert "allocated_points" in rows[0]
    assert "dag_violations" in rows[0]
    assert "fte_violations" in rows[0]
    assert "skill_violations" in rows[0]

    assert rows[0]["scenario"] == "scenario_a"
    assert rows[0]["allocated_points"] == "35"
    assert rows[1]["scenario"] == "scenario_b"
    assert rows[1]["allocated_points"] == "66"


# ============================================================================
# 5. Security & Safe Export Validation (Anti-Path Traversal)
# ============================================================================


def test_validate_safe_benchmark_path_allowed_extensions() -> None:
    """Safe benchmark path accepts valid relative paths with .json, .md, and .csv extensions."""
    repo_root = Path(__file__).resolve().parent.parent
    p1 = validate_safe_benchmark_path("reports/experiments/bench.json", base_dir=repo_root)
    assert p1.suffix == ".json"
    p2 = validate_safe_benchmark_path("reports/experiments/bench.md", base_dir=repo_root)
    assert p2.suffix == ".md"
    p3 = validate_safe_benchmark_path("reports/experiments/bench.csv", base_dir=repo_root)
    assert p3.suffix == ".csv"


@pytest.mark.parametrize(
    "forbidden_path",
    [
        "../../evil.csv",
        "../outside.json",
        "/etc/passwd.json",
        "C:\\Windows\\system32\\evil.csv",
    ],
)
def test_validate_safe_benchmark_path_blocks_traversal(forbidden_path: str) -> None:
    """Safe benchmark path blocks directory traversal attempts outside repository root."""
    repo_root = Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError, match="Security violation: path escapes repository"):
        validate_safe_benchmark_path(forbidden_path, base_dir=repo_root)


@pytest.mark.parametrize(
    "forbidden_ext_path",
    [
        "reports/experiments/exploit.py",
        "reports/experiments/malware.exe",
        "reports/experiments/data.txt",
        "reports/experiments/payload.sh",
    ],
)
def test_validate_safe_benchmark_path_blocks_forbidden_extensions(forbidden_ext_path: str) -> None:
    """Safe benchmark path blocks non-whitelisted extensions with security ValueError."""
    repo_root = Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError, match="Security violation: forbidden extension"):
        validate_safe_benchmark_path(forbidden_ext_path, base_dir=repo_root)


def test_export_benchmark_artifacts_saves_json_md_csv() -> None:
    """export_benchmark_artifacts safely exports JSON, Markdown, and CSV files."""
    report = run_benchmark_suite(
        config=BenchmarkConfig(scenarios=["a"], runs=1, offline_mock=True)
    )
    repo_root = Path(__file__).resolve().parent.parent
    prefix = f"test_export_phase9_{report.suite_id}"

    artifacts = export_benchmark_artifacts(
        report=report,
        base_filename=prefix,
        output_dir="reports/experiments",
    )

    try:
        assert "json" in artifacts
        assert "md" in artifacts
        assert "csv" in artifacts

        assert artifacts["json"].is_file()
        assert artifacts["md"].is_file()
        assert artifacts["csv"].is_file()

        json_content = json.loads(artifacts["json"].read_text(encoding="utf-8"))
        assert json_content["suite_id"] == report.suite_id
        assert len(json_content["summaries"]) == 1

        md_content = artifacts["md"].read_text(encoding="utf-8")
        assert "scenario_a" in md_content

        csv_content = artifacts["csv"].read_text(encoding="utf-8")
        assert "scenario_a" in csv_content
    finally:
        for path in artifacts.values():
            if path.exists():
                path.unlink()


# ============================================================================
# 6. Concurrency & Thread Isolation
# ============================================================================


def test_concurrent_benchmark_runs_thread_isolation() -> None:
    """Multiple concurrent executions isolate thread_id and do not corrupt metrics."""
    def _run_worker(idx: int) -> ScenarioBenchmarkSummary:
        scn = "scenario_a" if idx % 2 == 0 else "scenario_b"
        return run_scenario_benchmark(
            scn,
            config=BenchmarkConfig(scenarios=[scn], runs=1, offline_mock=True),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_run_worker, i) for i in range(4)]
        results = [f.result() for f in futures]

    assert len(results) == 4
    for i, res in enumerate(results):
        if i % 2 == 0:
            assert res.scenario == "scenario_a"
            assert res.mean_allocated_points == 35.0
        else:
            assert res.scenario == "scenario_b"
            assert res.mean_allocated_points == 66.0


# ============================================================================
# 7. CLI Integration (--benchmark Flag)
# ============================================================================


def test_cli_benchmark_happy_path(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI with --benchmark, --scenarios a,b, and --offline-mock returns exit code 0 and prints Markdown."""
    exit_code = run_cli(["--benchmark", "-sc", "a,b", "-N", "1", "--offline-mock"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Benchmark Suite Report" in captured.out
    assert "scenario_a" in captured.out
    assert "scenario_b" in captured.out
    assert "Tarefas (Total/Alocadas)" in captured.out


def test_cli_benchmark_circuit_breaker_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI with --benchmark on failing scenario (no trim) returns exit code 2."""
    exit_code = run_cli(
        ["--benchmark", "-sc", "b", "-N", "1", "--offline-mock", "--no-trim", "-r", "1"]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "REJECTED" in captured.out


def test_cli_benchmark_invalid_scenario_exit_code_1(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI with unknown scenario name returns exit code 1."""
    exit_code = run_cli(["--benchmark", "-sc", "unknown_foo", "--offline-mock"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CLI Execution Error" in captured.err or "Unknown scenario" in captured.err


def test_cli_benchmark_invalid_runs_exit_code_1(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI with invalid runs (0 or >50) returns exit code 1."""
    exit_code = run_cli(["--benchmark", "-sc", "a", "-N", "0", "--offline-mock"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CLI Execution Error" in captured.err or "runs must be between 1 and 50" in captured.err


def test_cli_benchmark_export_prefix_saves_artifacts() -> None:
    """CLI with --export-prefix exports JSON, Markdown, and CSV files safely."""
    prefix = "test_cli_bench_export_run"
    repo_root = Path(__file__).resolve().parent.parent
    expected_files = [
        repo_root / f"reports/experiments/{prefix}.json",
        repo_root / f"reports/experiments/{prefix}.md",
        repo_root / f"reports/experiments/{prefix}.csv",
    ]

    try:
        exit_code = run_cli(
            [
                "--benchmark",
                "-sc",
                "a",
                "-N",
                "1",
                "--offline-mock",
                "--export-prefix",
                prefix,
            ]
        )
        assert exit_code == 0
        for f in expected_files:
            assert f.is_file()
    finally:
        for f in expected_files:
            if f.exists():
                f.unlink()
