"""Comprehensive test suite for Phase 8: Hybrid LangSmith Observability & Executive CLI."""

import concurrent.futures
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from sprint_mas.data_loader import load_scenario
from sprint_mas.graph import build_sprint_graph, run_sprint_planning
from sprint_mas.telemetry import (
    DeliberationStep,
    DeliberationTraceReport,
    build_langsmith_run_config,
    configure_langsmith_tracing,
    extract_deliberation_trace,
    get_graph_mermaid,
    mask_secret,
    validate_safe_output_path,
)
from main import build_arg_parser, format_cli_report, normalize_scenario_name, run_cli


# ============================================================================
# 1. Happy Path: CLI & Scenarios A, B, and C
# ============================================================================


def test_cli_scenario_a_happy_path(capsys: pytest.CaptureFixture[str]) -> None:
    """When the CLI runs --scenario a (or scenario_a), it returns exit code 0 and displays the approved SprintPlan with 10 tasks and 35 pts."""
    exit_code = run_cli(["--scenario", "a", "--thread-id", "test-cli-a"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "APPROVED" in captured.out
    assert "35" in captured.out
    assert "10" in captured.out
    assert "TSK-001" in captured.out


def test_cli_scenario_b_with_trace_and_graph(capsys: pytest.CaptureFixture[str]) -> None:
    """When the CLI runs --scenario b with --show-trace and --show-graph, it returns exit code 0, displays the 2-pass trace (including replan), dev_D <= 10 pts, and the Mermaid diagram."""
    exit_code = run_cli(
        [
            "--scenario",
            "b",
            "--show-trace",
            "--show-graph",
            "--thread-id",
            "test-cli-b",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "APPROVED" in captured.out
    # Verify 2-pass deliberation trace is displayed
    assert "prioritizer -> allocator -> validator -> replan -> allocator -> validator -> supervisor" in captured.out
    assert "corrective_replan" in captured.out
    assert "dev_D" in captured.out
    # Verify Mermaid diagram is displayed
    assert "graph TD" in captured.out or "flowchart" in captured.out
    assert "prioritizer" in captured.out
    assert "replan" in captured.out


def test_cli_json_output_canonical_schema(capsys: pytest.CaptureFixture[str]) -> None:
    """When the CLI runs with --json, it prints valid canonical JSON containing sprint_plan, trace, and empty validation_errors."""
    exit_code = run_cli(["--scenario", "scenario_a", "--json", "--thread-id", "test-cli-json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "APPROVED"
    assert payload["validation_errors"] == []
    assert payload["sprint_plan"] is not None
    assert payload["sprint_plan"]["total_points"] == 35
    assert len(payload["sprint_plan"]["tasks"]) == 10

    trace = payload["trace"]
    assert trace["nodes_traversed"] == ["prioritizer", "allocator", "validator", "supervisor"]
    assert trace["execution_time_ms"] > 0.0
    assert trace["validation_attempts"] == 1
    assert trace["replan_triggered"] is False
    assert trace["is_approved"] is True


def test_cli_output_saves_json_artifact_inside_project() -> None:
    """When the CLI runs with --output reports/experiments/test_out.json, it saves the JSON artifact inside the project directory."""
    rel_out = "reports/experiments/test_cli_phase8_out.json"
    repo_root = Path(__file__).resolve().parent.parent
    target_file = repo_root / rel_out

    try:
        if target_file.exists():
            target_file.unlink()

        exit_code = run_cli(
            [
                "--scenario",
                "a",
                "--output",
                rel_out,
                "--thread-id",
                "test-cli-out",
            ]
        )
        assert exit_code == 0
        assert target_file.is_file()

        saved_data = json.loads(target_file.read_text(encoding="utf-8"))
        assert saved_data["status"] == "APPROVED"
        assert saved_data["sprint_plan"]["total_points"] == 35
        assert saved_data["trace"]["total_tasks_allocated"] == 10
    finally:
        if target_file.exists():
            target_file.unlink()


# ============================================================================
# 2. LangSmith Observability & BDI Traceability
# ============================================================================


def test_configure_langsmith_tracing_enabled_with_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """When LANGSMITH_TRACING=true and LANGSMITH_API_KEY is configured, configure_langsmith_tracing enables tracing and synchronizes LANGCHAIN_TRACING_V2 and LANGCHAIN_PROJECT."""
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_1234567890abcdef")
    monkeypatch.setenv("LANGSMITH_PROJECT", "reic-wesaac-test")

    result = configure_langsmith_tracing()

    assert result["tracing_enabled"] is True
    assert result["project_name"] == "reic-wesaac-test"
    assert result["api_key_masked"] == "lsv2...cdef"
    assert "lsv2_pt_1234567890abcdef" not in str(result)

    import os

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "reic-wesaac-test"
    assert os.environ["LANGCHAIN_PROJECT"] == "reic-wesaac-test"


def test_configure_langsmith_tracing_fallback_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """When LANGSMITH_TRACING=true but LANGSMITH_API_KEY is missing or empty, it safely falls back to local mode (tracing_enabled=False)."""
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    result = configure_langsmith_tracing()

    assert result["tracing_enabled"] is False
    assert result["api_key_masked"] == ""
    assert "Missing LANGSMITH_API_KEY" in result["reason"]

    import os

    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_build_langsmith_run_config_metadata_and_tags() -> None:
    """When build_langsmith_run_config is called, it generates RunnableConfig with thread_id, recursion_limit, run_name, BDI tags, and scenario metadata."""
    cfg = build_langsmith_run_config(
        thread_id="session-42",
        scenario_name="scenario_b",
        sprint_goal="Test BDI metadata",
        max_retries=3,
        sprint_days=10,
        points_per_day=2.0,
        tags=["custom-tag"],
        metadata={"experiment_id": "exp-01"},
    )

    assert cfg["configurable"] == {"thread_id": "session-42"}
    assert cfg["recursion_limit"] == 50
    assert cfg["run_name"] == "sprint-mas:scenario_b"
    assert "sprint-mas" in cfg["tags"]
    assert "bdi-architecture" in cfg["tags"]
    assert "scenario:scenario_b" in cfg["tags"]
    assert "custom-tag" in cfg["tags"]
    assert cfg["metadata"]["scenario"] == "scenario_b"
    assert cfg["metadata"]["thread_id"] == "session-42"
    assert cfg["metadata"]["sprint_goal"] == "Test BDI metadata"
    assert cfg["metadata"]["experiment_id"] == "exp-01"
    assert "beliefs:SprintState" in cfg["metadata"]["bdi_layers"]


def test_extract_deliberation_trace_scenario_b_seven_steps() -> None:
    """When extract_deliberation_trace analyzes the final state of full Scenario B, it identifies all 7 deliberation steps in order with replan_triggered=True and validation_attempts=2."""
    tasks_b, team_b = load_scenario("scenario_b")
    final_state = run_sprint_planning(
        backlog=tasks_b,
        team=team_b,
        thread_id="trace-b-test",
        scenario_name="scenario_b",
        max_retries=2,
    )

    report = extract_deliberation_trace(
        state=final_state,
        scenario="scenario_b",
        thread_id="trace-b-test",
        execution_time_ms=12.5,
        langsmith_enabled=False,
        langsmith_project="sprint-planning-mas",
    )

    assert isinstance(report, DeliberationTraceReport)
    assert report.nodes_traversed == [
        "prioritizer",
        "allocator",
        "validator",
        "replan",
        "allocator",
        "validator",
        "supervisor",
    ]
    assert len(report.deliberation_steps) == 7
    assert report.replan_triggered is True
    assert report.validation_attempts == 2
    assert report.is_approved is True
    assert report.total_tasks_allocated == 15
    assert report.total_points_allocated == 66

    bdi_phases = [step.bdi_phase for step in report.deliberation_steps]
    assert bdi_phases == [
        "desires",
        "intentions_draft",
        "governance_audit",
        "corrective_replan",
        "intentions_draft",
        "governance_audit",
        "intentions_consolidated",
    ]


# ============================================================================
# 3. Bounds, Circuit Breaker via CLI & Expected Errors
# ============================================================================


def test_cli_circuit_breaker_no_trim_returns_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    """When the CLI runs --scenario b --no-trim --max-retries 1, the circuit breaker trips, supervisor rejects, and CLI returns exit code 2 displaying FTE violations."""
    exit_code = run_cli(
        [
            "--scenario",
            "b",
            "--no-trim",
            "--max-retries",
            "1",
            "--thread-id",
            "test-cb-cli",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "REJECTED" in captured.out
    assert "FTE" in captured.out or "capacity" in captured.out.lower()


@pytest.mark.parametrize(
    "invalid_args",
    [
        ["--scenario", "inexistente"],
        ["--scenario", "a", "--max-retries", "-1"],
        ["--scenario", "a", "--max-retries", "11"],
        ["--scenario", "a", "--sprint-days", "0"],
        ["--scenario", "a", "--points-per-day", "-2.0"],
    ],
)
def test_cli_invalid_arguments_return_non_zero_without_traceback(
    invalid_args: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When invalid arguments are passed, CLI returns non-zero error code with a clean message and no raw traceback."""
    exit_code = run_cli(invalid_args)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Traceback (most recent call last)" not in captured.err
    assert "Traceback (most recent call last)" not in captured.out
    assert "Error" in captured.err or "error" in captured.err.lower()


# ============================================================================
# 4. Defensive Security: Anti-Path Traversal, Secrets & Mass Assignment
# ============================================================================


@pytest.mark.parametrize(
    "malicious_path",
    [
        "../outside.json",
        "../../evil.json",
        "C:/Windows/System32/evil.json",
        "/etc/passwd.json",
        "reports/malicious_script.py",
        "reports/executable.exe",
        "",
    ],
)
def test_validate_safe_output_path_blocks_traversal_and_bad_extensions(malicious_path: str) -> None:
    """When --output attempts to write outside the project directory or with a forbidden extension, it blocks with a security ValueError."""
    with pytest.raises(ValueError, match="Security violation"):
        validate_safe_output_path(malicious_path)


def test_mask_secret_never_exposes_raw_keys() -> None:
    """When mask_secret or telemetry config is inspected, secret keys are never exposed in plain text."""
    assert mask_secret(None) == ""
    assert mask_secret("") == ""
    assert mask_secret("   ") == ""
    assert mask_secret("short") == "***"
    assert mask_secret("12345678") == "***"

    raw_secret = "gsk_live_9876543210secretkeyXYZ"
    masked = mask_secret(raw_secret)
    assert masked == "gsk_...yXYZ"
    assert raw_secret not in masked


def test_telemetry_models_forbid_extra_fields() -> None:
    """When DeliberationStep or DeliberationTraceReport receive unauthorized extra fields, Pydantic extra='forbid' rejects the payload."""
    with pytest.raises(ValidationError):
        DeliberationStep(
            step_index=1,
            agent_node="prioritizer",
            bdi_phase="desires",
            headline="Header",
            content_preview="Preview",
            extra_injected_field="malicious",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        DeliberationTraceReport(
            run_id="run-1",
            thread_id="t-1",
            scenario="scenario_a",
            langsmith_enabled=False,
            langsmith_project="proj",
            execution_time_ms=1.0,
            nodes_traversed=["prioritizer"],
            validation_attempts=1,
            replan_triggered=False,
            is_approved=True,
            total_tasks_allocated=10,
            total_points_allocated=35,
            deliberation_steps=[],
            graph_mermaid="graph TD",
            unauthorized_admin_flag=True,  # type: ignore[call-arg]
        )


# ============================================================================
# 5. Simultaneous Concurrency
# ============================================================================


def test_concurrent_telemetry_and_cli_executions() -> None:
    """When 10 telemetry/planning executions run simultaneously in parallel (ThreadPoolExecutor), each generates an isolated DeliberationTraceReport without state collision."""
    tasks_a, team_a = load_scenario("scenario_a")
    tasks_b, team_b = load_scenario("scenario_b")

    def _worker(idx: int) -> DeliberationTraceReport:
        if idx % 2 == 0:
            state = run_sprint_planning(
                backlog=tasks_a,
                team=team_a,
                thread_id=f"conc-a-{idx}",
                scenario_name="scenario_a",
            )
            return extract_deliberation_trace(
                state=state,
                scenario="scenario_a",
                thread_id=f"conc-a-{idx}",
                execution_time_ms=float(idx + 1),
            )
        else:
            state = run_sprint_planning(
                backlog=tasks_b,
                team=team_b,
                thread_id=f"conc-b-{idx}",
                scenario_name="scenario_b",
            )
            return extract_deliberation_trace(
                state=state,
                scenario="scenario_b",
                thread_id=f"conc-b-{idx}",
                execution_time_ms=float(idx + 1),
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_worker, i) for i in range(10)]
        reports = [f.result() for f in futures]

    assert len(reports) == 10
    for i, rep in enumerate(reports):
        if i % 2 == 0:
            assert rep.scenario == "scenario_a"
            assert rep.thread_id == f"conc-a-{i}"
            assert rep.replan_triggered is False
            assert rep.validation_attempts == 1
            assert rep.total_points_allocated == 35
            assert len(rep.deliberation_steps) == 4
        else:
            assert rep.scenario == "scenario_b"
            assert rep.thread_id == f"conc-b-{i}"
            assert rep.replan_triggered is True
            assert rep.validation_attempts == 2
            assert rep.total_points_allocated == 66
            assert len(rep.deliberation_steps) == 7
