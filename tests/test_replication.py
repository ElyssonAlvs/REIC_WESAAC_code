"""Comprehensive test suite for Phase 12: Scientific Replication Package, Postman Collection & Governance (sprint_mas/replication.py & main.py)."""

import csv
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from main import run_cli
from sprint_mas.benchmarks import validate_safe_benchmark_path
from sprint_mas.replication import (
    ReplicationPackageConfig,
    ScientificReplicationBundle,
    export_replication_artifacts,
    format_replication_csv,
    format_replication_latex,
    format_replication_markdown,
    run_scientific_replication,
)


# ============================================================================
# 1. Pydantic v2 Models & Immutability (extra="forbid")
# ============================================================================


def test_replication_package_config_defaults_and_normalization() -> None:
    """When ReplicationPackageConfig is created with default or aliased scenarios, it normalizes scenario names."""
    cfg = ReplicationPackageConfig()
    assert cfg.scenarios == ["scenario_a", "scenario_b", "scenario_c"]
    assert cfg.runs == 1
    assert cfg.offline_mock is True
    assert cfg.max_retries == 2
    assert cfg.sprint_days == 10
    assert cfg.points_per_day == 2.0
    assert cfg.strict is False
    assert cfg.enable_scope_trimming is True

    # Test alias normalization
    cfg_alias = ReplicationPackageConfig(scenarios=["a", "scenario_b.json", "c"])
    assert cfg_alias.scenarios == ["scenario_a", "scenario_b", "scenario_c"]


def test_replication_package_config_forbids_extra_fields() -> None:
    """When extra fields are provided to ReplicationPackageConfig, Pydantic ConfigDict(extra='forbid') rejects them."""
    with pytest.raises(ValidationError):
        ReplicationPackageConfig(
            scenarios=["scenario_a"],
            unauthorized_field="exploit",
        )


@pytest.mark.parametrize(
    "invalid_runs",
    [0, -1, 51, 100],
)
def test_replication_package_config_runs_bounds(invalid_runs: int) -> None:
    """When runs is outside [1, 50], ReplicationPackageConfig raises ValidationError."""
    with pytest.raises(ValidationError):
        ReplicationPackageConfig(runs=invalid_runs)


@pytest.mark.parametrize(
    ("param_name", "invalid_value"),
    [
        ("sprint_days", 0),
        ("sprint_days", -5),
        ("points_per_day", 0.0),
        ("points_per_day", -1.5),
        ("max_retries", -1),
        ("max_retries", 11),
    ],
)
def test_replication_package_config_numeric_bounds(param_name: str, invalid_value: float) -> None:
    """When numeric configuration parameters are out of bounds, ValidationError is raised."""
    with pytest.raises(ValidationError):
        ReplicationPackageConfig(**{param_name: invalid_value})


def test_replication_package_config_empty_or_unknown_scenarios_rejected() -> None:
    """When scenarios list is empty or contains non-existent scenario names, ValueError is raised."""
    with pytest.raises(ValueError, match="Scenarios list cannot be empty"):
        ReplicationPackageConfig(scenarios=[])

    with pytest.raises(ValueError, match="Unknown scenario"):
        ReplicationPackageConfig(scenarios=["non_existent_scenario_xyz"])


def test_scientific_replication_bundle_forbids_extra_fields() -> None:
    """When extra fields are injected into ScientificReplicationBundle, ConfigDict(extra='forbid') rejects them."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    bundle_dict = bundle.model_dump()
    bundle_dict["injected_backdoor"] = "hostile_payload"

    with pytest.raises(ValidationError):
        ScientificReplicationBundle(**bundle_dict)


def test_scientific_replication_bundle_canonical_json_serialization() -> None:
    """When ScientificReplicationBundle is serialized to JSON, it produces valid, parseable canonical JSON."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    json_str = bundle.model_dump_json(indent=2)
    parsed = json.loads(json_str)

    assert parsed["bundle_id"] == bundle.bundle_id
    assert parsed["is_fully_reproduced"] is True
    assert parsed["benchmark_report"]["suite_id"] == bundle.benchmark_report.suite_id
    assert parsed["empirical_report"]["report_id"] == bundle.empirical_report.report_id
    assert parsed["security_report"]["audit_id"] == bundle.security_report.audit_id


# ============================================================================
# 2. End-to-End Scientific Replication Orchestration
# ============================================================================


def test_run_scientific_replication_happy_path_all_scenarios() -> None:
    """When run_scientific_replication is executed across A, B, and C with offline_mock=True, all stages succeed."""
    cfg = ReplicationPackageConfig(
        scenarios=["scenario_a", "scenario_b", "scenario_c"],
        runs=1,
        offline_mock=True,
    )
    bundle = run_scientific_replication(config=cfg)

    assert bundle.is_fully_reproduced is True
    assert bundle.bottleneck_mitigated is True
    assert bundle.benchmark_report.all_approved is True
    assert bundle.security_report.all_passed is True
    assert len(bundle.benchmark_report.summaries) == 3
    assert len(bundle.empirical_report.comparisons) == 3
    assert len(bundle.summary_notes) >= 4
    assert any("FULLY REPRODUCED" in note for note in bundle.summary_notes)


def test_run_scientific_replication_single_scenario_a() -> None:
    """When run_scientific_replication runs only Scenario A, it successfully reproduces and marks fully reproduced."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    assert bundle.is_fully_reproduced is True
    assert len(bundle.benchmark_report.summaries) == 1
    assert bundle.benchmark_report.summaries[0].scenario == "scenario_a"


def test_run_scientific_replication_scenario_b_bottleneck_mitigation() -> None:
    """When run_scientific_replication evaluates Scenario B, Section 6.3 qualitative bottleneck mitigation is proved."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_b"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    assert bundle.is_fully_reproduced is True
    assert bundle.bottleneck_mitigated is True

    b_comp = next((c for c in bundle.empirical_report.comparisons if c.scenario == "scenario_b"), None)
    assert b_comp is not None
    assert b_comp.bottleneck_analysis is not None
    assert b_comp.bottleneck_analysis.backend_density_pct == 63.33
    assert b_comp.bottleneck_analysis.dev_c_backend_tasks_absorbed == 3
    assert b_comp.bottleneck_analysis.dev_c_backend_points_absorbed == 19
    assert b_comp.bottleneck_analysis.dev_d_allocated_points == 10.0
    assert b_comp.bottleneck_analysis.dev_d_capacity_respected is True
    assert b_comp.bottleneck_analysis.fullstack_mitigation_active is True


# ============================================================================
# 3. Formatters & Multi-Format Exporters
# ============================================================================


def test_format_replication_markdown() -> None:
    """format_replication_markdown generates comprehensive executive markdown with all 5 sections."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a", "scenario_b"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    md = format_replication_markdown(bundle)

    assert "# Pacote de Reprodutibilidade Científica — WESAAC 2025 & REIC 2026" in md
    assert "REPRODUCED (100% COMPLIANT)" in md
    assert bundle.bundle_id in md
    assert "## 1. Sumário Executivo da Reprodução Experimental" in md
    assert "## 2. Bateria de Benchmarks Automatizados" in md
    assert "## 3. Avaliação Empírica Cruzada & Confronto com Linhas de Base" in md
    assert "## 4. Auditoria de Segurança do Pentágono" in md
    assert "## 5. Tabela Canônica para Publicação Acadêmica (LaTeX Booktabs)" in md
    assert "\\begin{table}" in md
    assert "\\end{table}" in md


def test_format_replication_latex() -> None:
    """format_replication_latex generates valid LaTeX booktabs table for paper insertion."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_b"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    tex = format_replication_latex(bundle)

    assert "\\begin{table}" in tex
    assert "\\toprule" in tex
    assert "\\midrule" in tex
    assert "\\bottomrule" in tex
    assert "\\end{table}" in tex
    assert "Scenario\\_B" in tex or "scenario_b" in tex or "Scenario B" in tex


def test_format_replication_csv_canonical_headers_and_na() -> None:
    """format_replication_csv generates parseable CSV with explicit provider, model, and N/A handling."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a", "scenario_b", "scenario_c"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    csv_text = format_replication_csv(bundle)
    rows = list(csv.reader(csv_text.strip().splitlines()))
    headers = rows[0]

    assert headers[0] == "bundle_id"
    assert "scenario" in headers
    assert "provider" in headers
    assert "model_name" in headers
    assert "speedup_vs_manual" in headers
    assert "dev_c_backend_absorbed_pts" in headers
    assert "dev_d_capacity_respected" in headers
    assert "fully_reproduced" in headers

    # Verify scenario A row has "N/A" for manual_time_ms rather than empty commas
    row_a = next((r for r in rows[1:] if r[2] == "scenario_a"), None)
    assert row_a is not None
    # manual_time_ms is column index 6
    assert row_a[headers.index("manual_time_ms")] == "N/A"
    assert row_a[headers.index("speedup_vs_manual")] == "N/A"
    assert row_a[headers.index("dev_c_backend_absorbed_pts")] == "N/A"

    # Verify scenario B row has real values
    row_b = next((r for r in rows[1:] if r[2] == "scenario_b"), None)
    assert row_b is not None
    assert row_b[headers.index("manual_time_ms")] == "765000.0"
    assert row_b[headers.index("dev_c_backend_absorbed_pts")] == "19"
    assert row_b[headers.index("dev_d_capacity_respected")] == "True"


def test_export_replication_artifacts_saves_all_four_files() -> None:
    """export_replication_artifacts safely exports .json, .md, .csv, and .tex artifacts."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    prefix = "test_export_repl_suite"
    repo_root = Path(__file__).resolve().parent.parent
    target_dir = repo_root / "reports" / "experiments"

    try:
        artifacts = export_replication_artifacts(
            bundle,
            base_filename=prefix,
            output_dir=target_dir,
            export_json=True,
            export_md=True,
            export_csv=True,
            export_tex=True,
        )

        assert set(artifacts.keys()) == {"json", "md", "csv", "tex"}
        for fmt, p in artifacts.items():
            assert p.is_file(), f"Expected artifact {fmt} at {p} to exist."
            content = p.read_text(encoding="utf-8")
            assert len(content) > 0

        # Anti-CRCRLF line-ending defensive assertion
        raw_csv_bytes = artifacts["csv"].read_bytes()
        assert b"\r\r\n" not in raw_csv_bytes, "Replication CSV artifact contains duplicate carriage return b'\\r\\r\\n'!"
        with open(artifacts["csv"], "r", encoding="utf-8", newline="") as f:
            reader = list(csv.reader(f))
            assert len(reader) >= 2
            expected_cols = len(reader[0])
            for idx, row in enumerate(reader):
                assert len(row) == expected_cols, f"Row {idx+1} has {len(row)} columns, expected {expected_cols}"

    finally:
        for ext in [".json", ".md", ".csv", ".tex"]:
            f = target_dir / f"{prefix}{ext}"
            if f.exists():
                f.unlink()


@pytest.mark.parametrize(
    "hostile_path",
    [
        "../../evil_bundle",
        "../outside",
        "/etc/passwd",
        r"..\..\reports\experiments\exploit",
        "reports/malicious.py",
        "reports/executable.exe",
    ],
)
def test_export_replication_artifacts_blocks_path_traversal(hostile_path: str) -> None:
    """When base_filename attempts directory traversal or bad extensions, ValueError is raised."""
    cfg = ReplicationPackageConfig(scenarios=["scenario_a"], runs=1, offline_mock=True)
    bundle = run_scientific_replication(config=cfg)

    with pytest.raises(ValueError):
        export_replication_artifacts(bundle, base_filename=hostile_path)


# ============================================================================
# 4. Executive CLI Integration Tests (main.py --reproduce-paper)
# ============================================================================


def test_cli_reproduce_paper_happy_path() -> None:
    """When CLI runs --reproduce-paper with --offline-mock, returns exit code 0."""
    exit_code = run_cli([
        "--reproduce-paper",
        "--offline-mock",
        "-s",
        "a",
        "--thread-id",
        "test-repl-cli",
    ])
    assert exit_code == 0


def test_cli_reproduce_paper_alias_flags() -> None:
    """When CLI is invoked via -R or --replicate, returns exit code 0."""
    exit_code_r = run_cli([
        "-R",
        "--offline-mock",
        "-s",
        "a",
        "--thread-id",
        "test-repl-r",
    ])
    assert exit_code_r == 0

    exit_code_repl = run_cli([
        "--replicate",
        "--offline-mock",
        "-s",
        "a",
        "--thread-id",
        "test-repl-replicate",
    ])
    assert exit_code_repl == 0


def test_cli_reproduce_paper_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """When CLI runs --reproduce-paper with --json, emits valid JSON containing is_fully_reproduced: true."""
    exit_code = run_cli([
        "--reproduce-paper",
        "--offline-mock",
        "--json",
        "-s",
        "a",
        "--thread-id",
        "test-repl-json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["is_fully_reproduced"] is True
    assert "benchmark_report" in data
    assert "empirical_report" in data
    assert "security_report" in data


def test_cli_reproduce_paper_export_prefix() -> None:
    """When CLI runs --reproduce-paper with --export-prefix, saves all 4 artifacts under reports/experiments/replication/."""
    prefix = "test_cli_repl_artifacts"
    repo_root = Path(__file__).resolve().parent.parent
    target_dir = repo_root / "reports" / "experiments" / "replication"

    try:
        exit_code = run_cli([
            "--reproduce-paper",
            "--offline-mock",
            "--export-prefix",
            prefix,
            "-s",
            "a",
            "--thread-id",
            "test-cli-prefix",
        ])
        assert exit_code == 0

        for ext in [".json", ".md", ".csv", ".tex"]:
            expected_file = target_dir / f"{prefix}{ext}"
            assert expected_file.is_file(), f"Expected file {expected_file} to exist."
    finally:
        for ext in [".json", ".md", ".csv", ".tex"]:
            expected_file = target_dir / f"{prefix}{ext}"
            if expected_file.exists():
                expected_file.unlink()


def test_cli_reproduce_paper_custom_output_safe_and_unsafe() -> None:
    """When CLI runs with safe relative --output, file is saved; when path traversal is attempted, returns 1."""
    rel_out = "reports/experiments/test_cli_repl_out.json"
    repo_root = Path(__file__).resolve().parent.parent
    target_file = repo_root / rel_out

    try:
        exit_code = run_cli([
            "--reproduce-paper",
            "--offline-mock",
            "--output",
            rel_out,
            "-s",
            "a",
            "--thread-id",
            "test-cli-output-safe",
        ])
        assert exit_code == 0
        assert target_file.is_file()

        # Malicious output path escaping repo
        exit_code_malicious = run_cli([
            "--reproduce-paper",
            "--offline-mock",
            "--output",
            "../../evil_replication.json",
        ])
        assert exit_code_malicious == 1
    finally:
        if target_file.exists():
            target_file.unlink()


@pytest.mark.parametrize(
    ("cli_arg", "bad_val"),
    [
        ("--runs", "0"),
        ("--runs", "51"),
        ("--sprint-days", "0"),
        ("--points-per-day", "0.0"),
        ("--max-retries", "-1"),
        ("--max-retries", "11"),
    ],
)
def test_cli_reproduce_paper_invalid_arguments_return_exit_code_1(cli_arg: str, bad_val: str) -> None:
    """When invalid numeric bounds are supplied to CLI --reproduce-paper, returns exit code 1."""
    exit_code = run_cli(["--reproduce-paper", "--offline-mock", cli_arg, bad_val])
    assert exit_code == 1


# ============================================================================
# 5. Postman Collection v2.1.0 Verification
# ============================================================================


def test_postman_collection_structure_and_assertions() -> None:
    """When Postman collection JSON is validated, it complies with v2.1.0 schema with 5 folders and JavaScript tests."""
    repo_root = Path(__file__).resolve().parent.parent
    col_path = repo_root / "docs" / "collections" / "sprint_mas_postman_collection.json"

    assert col_path.is_file(), f"Postman collection file {col_path} must exist."

    collection = json.loads(col_path.read_text(encoding="utf-8"))

    # Validate Schema and Metadata
    assert collection["info"]["schema"] == "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    assert "WESAAC 2025" in collection["info"]["name"]
    assert "REIC 2026" in collection["info"]["name"]

    folders = collection["item"]
    assert len(folders) == 5

    folder_names = [f["name"] for f in folders]
    assert "1. Cenários de Planejamento (A, B, C)" in folder_names
    assert "2. Benchmarks Automatizados" in folder_names
    assert "3. Avaliação Empírica & Comparativo Humano" in folder_names
    assert "4. Auditoria de Segurança do Pentágono" in folder_names
    assert "5. Pacote de Reprodutibilidade Científica" in folder_names

    # Verify that requests have pm.test assertion scripts and status 200
    for folder in folders:
        for request_item in folder["item"]:
            assert "request" in request_item
            assert "event" in request_item
            test_events = [e for e in request_item["event"] if e.get("listen") == "test"]
            assert len(test_events) >= 1
            script_lines = test_events[0]["script"]["exec"]
            script_joined = "\n".join(script_lines)
            assert "pm.test" in script_joined
            assert "pm.response" in script_joined
