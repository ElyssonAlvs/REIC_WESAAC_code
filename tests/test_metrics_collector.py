"""Tests for LangSmith Metrics Extractor and Multi-Model Consolidation (tests/test_metrics_collector.py)."""

from datetime import datetime, timezone
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from sprint_mas.benchmarks import validate_safe_benchmark_path
from sprint_mas.security_audit import verify_pydantic_models_hardening


def _make_mock_run(
    run_id: str = "run-001",
    name: str = "sprint-mas:scenario_b",
    tags: list[str] | None = None,
    metadata: dict | None = None,
    extra: dict | None = None,
    latency_sec: float = 1.5,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int | None = None,
    total_cost: float | None = 0.00125,
    status: str = "success",
    error: str | None = None,
):
    """Helper to build a mock LangSmith run object."""
    actual_total = total_tokens if total_tokens is not None else (prompt_tokens + completion_tokens)
    run = MagicMock()
    run.id = run_id
    run.name = name
    run.tags = tags or ["sprint-mas", "scenario:scenario_b", "reic-2026"]

    scenario = "scenario_b"
    if tags:
        for t in tags:
            if t.startswith("scenario:"):
                scenario = t.split("scenario:", 1)[1]
    elif "scenario_a" in name:
        scenario = "scenario_a"
    elif "scenario_c" in name:
        scenario = "scenario_c"

    run.metadata = metadata or {"scenario": scenario, "model": "openai/gpt-oss-120b"}
    run.extra = extra or {
        "ls_model_name": run.metadata.get("model", "openai/gpt-oss-120b"),
        "metadata": run.metadata,
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": actual_total,
        },
    }
    run.latency = latency_sec
    run.start_time = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)
    run.end_time = datetime(2026, 11, 6, 12, 0, int(latency_sec), int((latency_sec % 1) * 1e6), tzinfo=timezone.utc)
    run.prompt_tokens = prompt_tokens
    run.completion_tokens = completion_tokens
    run.total_tokens = actual_total
    run.total_cost = total_cost
    run.status = status
    run.error = error
    return run


# ===========================================================================
# 1. Conexão e Consulta Paginada à API do LangSmith
# ===========================================================================


def test_pull_langsmith_metrics_paginated_and_reads_project():
    """Quando pull_langsmith_metrics é invocado com API key válida, obtém UUID e filtra execuções LLM reais."""
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    mock_client = MagicMock()
    mock_project = MagicMock()
    mock_project.id = "proj-uuid-1234-5678"
    mock_client.read_project.return_value = mock_project

    mock_runs = [
        _make_mock_run(run_id="run-1", latency_sec=2.0),
        _make_mock_run(run_id="run-2", latency_sec=3.0),
    ]
    mock_client.list_runs.return_value = iter(mock_runs)

    report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=mock_client)

    mock_client.read_project.assert_called_once_with(project_name="REIC_WESAAC_code")
    mock_client.list_runs.assert_called_once_with(
        project_id="proj-uuid-1234-5678",
        filter='and(eq(run_type, "llm"), gt(total_tokens, 0))',
    )
    assert report.project_name == "REIC_WESAAC_code"
    assert report.total_runs_analyzed == 2
    assert report.all_passed is True
    assert len(report.metrics) == 1
    assert report.metrics[0].model_name == "openai/gpt-oss-120b"
    assert report.metrics[0].scenario == "scenario_b"
    assert report.metrics[0].runs_count == 2


def test_pull_langsmith_metrics_handles_rate_limit_and_auth_error_graciously():
    """Quando a API retorna HTTP 429 ou erro de autenticação, captura graciosamente sem crashar."""
    from langsmith.utils import LangSmithRateLimitError
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    mock_client = MagicMock()
    mock_client.read_project.side_effect = LangSmithRateLimitError("Rate limit exceeded for runs endpoint")

    report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=mock_client)

    assert report.all_passed is False
    assert report.total_runs_analyzed == 0
    assert len(report.metrics) == 0
    assert any("Rate limit exceeded" in n for n in report.notes)


def test_pull_langsmith_metrics_missing_api_key_without_client():
    """Quando client é None e não há API key no ambiente, retorna relatório seguro com status de erro."""
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    with patch.dict(os.environ, {}, clear=True):
        report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=None)

    assert report.all_passed is False
    assert report.total_runs_analyzed == 0
    assert any("LANGSMITH_API_KEY" in n for n in report.notes)


def test_pull_langsmith_metrics_filters_non_sprint_mas_runs():
    """Filtra runs pertencentes a outros sistemas ou sem identificação de cenário sprint-mas."""
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    mock_client = MagicMock()
    mock_project = MagicMock()
    mock_project.id = "proj-filter-uuid"
    mock_client.read_project.return_value = mock_project

    valid_run = _make_mock_run(run_id="valid-1", name="sprint-mas:scenario_a", tags=["scenario:scenario_a"])
    unrelated_run = MagicMock()
    unrelated_run.name = "unrelated_web_scraper"
    unrelated_run.tags = ["crawler", "raw-html"]
    unrelated_run.metadata = {}
    unrelated_run.extra = {}

    mock_client.list_runs.return_value = [valid_run, unrelated_run]

    report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=mock_client)

    assert report.total_runs_analyzed == 1
    assert len(report.metrics) == 1
    assert report.metrics[0].scenario == "scenario_a"


def test_pull_langsmith_metrics_filters_offline_mock_and_zero_tokens():
    """Filtra runs originadas do OfflineFallbackChatModel ou com 0 tokens totais."""
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    mock_client = MagicMock()
    mock_project = MagicMock()
    mock_project.id = "proj-mock-filter-uuid"
    mock_client.read_project.return_value = mock_project

    mock_llm_run = _make_mock_run(
        run_id="mock-1",
        name="OfflineFallbackChatModel",
        tags=["sprint-mas", "scenario:scenario_b"],
        metadata={"model": "OfflineFallbackChatModel", "scenario": "scenario_b"},
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    zero_token_run = _make_mock_run(
        run_id="zero-1",
        name="sprint-mas:scenario_b",
        tags=["sprint-mas", "scenario:scenario_b"],
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    valid_llm_run = _make_mock_run(
        run_id="valid-real-1",
        name="ChatGroq",
        tags=["sprint-mas", "scenario:scenario_b"],
        metadata={"model": "openai/gpt-oss-20b", "scenario": "scenario_b"},
        extra={"metadata": {"ls_model_name": "openai/gpt-oss-20b"}},
        prompt_tokens=500,
        completion_tokens=100,
        total_tokens=600,
    )

    mock_client.list_runs.return_value = [mock_llm_run, zero_token_run, valid_llm_run]

    report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=mock_client)

    assert report.total_runs_analyzed == 1
    assert len(report.metrics) == 1
    assert report.metrics[0].model_name == "openai/gpt-oss-20b"
    assert report.metrics[0].scenario == "scenario_b"
    assert report.metrics[0].runs_count == 1
    assert report.metrics[0].mean_total_tokens == 600.0


def test_extract_scenario_from_inputs_when_custom():
    """Infere o cenário canônico (a, b ou c) a partir das mensagens quando a tag/metadata for 'custom'."""
    from sprint_mas.metrics_collector import _extract_scenario

    run_custom_a = MagicMock()
    run_custom_a.tags = ["scenario:custom"]
    run_custom_a.name = "ChatGroq"
    run_custom_a.metadata = {"scenario": "custom"}
    run_custom_a.inputs = {"messages": "Sprint backlog contains tasks: TSK-001 (5 pts), TSK-002 (3 pts)"}

    run_custom_b = MagicMock()
    run_custom_b.tags = ["scenario:custom"]
    run_custom_b.name = "ChatGroq"
    run_custom_b.metadata = {"scenario": "custom"}
    run_custom_b.inputs = {"messages": "Sprint backlog contains tasks: TSK-101 (8 pts), TSK-102 (5 pts)"}

    run_custom_c = MagicMock()
    run_custom_c.tags = []
    run_custom_c.name = "ChatGroq"
    run_custom_c.metadata = {}
    run_custom_c.inputs = {"messages": "Sprint backlog contains tasks: TSK-201 (13 pts), TSK-202 (8 pts)"}

    assert _extract_scenario(run_custom_a) == "scenario_a"
    assert _extract_scenario(run_custom_b) == "scenario_b"
    assert _extract_scenario(run_custom_c) == "scenario_c"


# ===========================================================================
# 2. Normalização, Agregação Multi-Modelo e Contratos Pydantic v2
# ===========================================================================


def test_pydantic_models_reject_extra_fields():
    """ModelScenarioMetric e LangSmithMetricsSuiteReport rejeitam campos desconhecidos via extra='forbid'."""
    from sprint_mas.metrics_collector import LangSmithMetricsSuiteReport, ModelScenarioMetric

    with pytest.raises(ValidationError):
        ModelScenarioMetric(
            model_name="test-model",
            scenario="scenario_b",
            runs_count=1,
            mean_duration_ms=100.0,
            median_duration_ms=100.0,
            p95_duration_ms=100.0,
            mean_prompt_tokens=50.0,
            mean_completion_tokens=25.0,
            mean_total_tokens=75.0,
            total_cost_usd=0.001,
            success_rate_pct=100.0,
            unauthorized_field="malicious_payload",
        )

    with pytest.raises(ValidationError):
        LangSmithMetricsSuiteReport(
            report_id="rep-1",
            project_name="proj",
            extracted_at="2026-11-06T00:00:00Z",
            total_runs_analyzed=1,
            metrics=[],
            all_passed=True,
            notes=[],
            injected_key=123,
        )


def test_multi_model_scenario_aggregation_statistics():
    """Calcula corretamente médias, mediana, P95, tokens médios e custo acumulado por modelo e cenário."""
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    mock_client = MagicMock()
    mock_project = MagicMock()
    mock_project.id = "proj-agg-uuid"
    mock_client.read_project.return_value = mock_project

    # 3 runs for gpt-oss-120b on scenario_b: latencies = 1000ms, 2000ms, 3000ms
    r1 = _make_mock_run(run_id="r1", latency_sec=1.0, prompt_tokens=100, completion_tokens=50, total_cost=0.001)
    r2 = _make_mock_run(run_id="r2", latency_sec=2.0, prompt_tokens=200, completion_tokens=100, total_cost=0.002)
    r3 = _make_mock_run(run_id="r3", latency_sec=3.0, prompt_tokens=300, completion_tokens=150, total_cost=0.003)

    # 1 run for qwen3.8-27b on scenario_c
    r4 = _make_mock_run(
        run_id="r4",
        name="sprint-mas:scenario_c",
        tags=["sprint-mas", "scenario:scenario_c"],
        metadata={"scenario": "scenario_c", "model": "qwen/qwen3.8-27b"},
        extra={"ls_model_name": "qwen/qwen3.8-27b"},
        latency_sec=1.2,
        prompt_tokens=80,
        completion_tokens=40,
        total_cost=0.0005,
    )

    mock_client.list_runs.return_value = [r1, r2, r3, r4]

    report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=mock_client)

    assert report.total_runs_analyzed == 4
    assert len(report.metrics) == 2

    m_120b = next(m for m in report.metrics if m.model_name == "openai/gpt-oss-120b")
    assert m_120b.scenario == "scenario_b"
    assert m_120b.runs_count == 3
    assert m_120b.mean_duration_ms == 2000.0
    assert m_120b.median_duration_ms == 2000.0
    assert m_120b.p95_duration_ms == 2900.0
    assert m_120b.mean_prompt_tokens == 200.0
    assert m_120b.mean_completion_tokens == 100.0
    assert m_120b.mean_total_tokens == 300.0
    assert m_120b.total_cost_usd == 0.006
    assert m_120b.success_rate_pct == 100.0

    m_qwen = next(m for m in report.metrics if m.model_name == "qwen/qwen3.8-27b")
    assert m_qwen.scenario == "scenario_c"
    assert m_qwen.runs_count == 1
    assert m_qwen.mean_duration_ms == 1200.0
    assert m_qwen.p95_duration_ms == 1200.0
    assert m_qwen.total_cost_usd == 0.0005


def test_cost_normalization_when_none_or_missing():
    """Runs sem dados de custo (ex: Ollama local) são normalizadas para 0.00000 sem falha."""
    from sprint_mas.metrics_collector import pull_langsmith_metrics

    mock_client = MagicMock()
    mock_project = MagicMock()
    mock_project.id = "proj-cost-uuid"
    mock_client.read_project.return_value = mock_project

    ollama_run = _make_mock_run(
        run_id="ollama-1",
        name="sprint-mas:scenario_a",
        tags=["sprint-mas", "scenario:scenario_a", "llama3"],
        metadata={"scenario": "scenario_a", "model": "llama3:latest"},
        extra={"ls_model_name": "llama3:latest"},
        total_cost=None,
    )
    mock_client.list_runs.return_value = [ollama_run]

    report = pull_langsmith_metrics(project_name="REIC_WESAAC_code", client=mock_client)

    assert len(report.metrics) == 1
    assert report.metrics[0].total_cost_usd == 0.0


# ===========================================================================
# 3. Exportação Quádrupla Segura e Sem Erros de Quebra de Linha (CRCRLF)
# ===========================================================================


def test_export_artifacts_generates_all_four_files(tmp_path: Path):
    """export_metrics_artifacts grava sincronizadamente .json, .md, .csv e .tex."""
    from sprint_mas.metrics_collector import (
        LangSmithMetricsSuiteReport,
        ModelScenarioMetric,
        export_metrics_artifacts,
    )

    report = LangSmithMetricsSuiteReport(
        report_id="test-exp-01",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=1,
        metrics=[
            ModelScenarioMetric(
                model_name="openai/gpt-oss-120b",
                scenario="scenario_b",
                runs_count=1,
                mean_duration_ms=1500.0,
                median_duration_ms=1500.0,
                p95_duration_ms=1500.0,
                mean_prompt_tokens=120.0,
                mean_completion_tokens=60.0,
                mean_total_tokens=180.0,
                total_cost_usd=0.0015,
                success_rate_pct=100.0,
            )
        ],
        all_passed=True,
        notes=["Test export run"],
    )

    artifacts = export_metrics_artifacts(report, base_filename="custom_summary", output_dir=tmp_path)

    assert set(artifacts.keys()) == {"json", "md", "csv", "tex"}
    for ext, path in artifacts.items():
        assert path.exists()
        assert path.stat().st_size > 0


def test_csv_zero_crcrlf_and_uniform_columns(tmp_path: Path):
    """Garante 0 ocorrências de \\r\\r\\n no CSV e número uniforme de colunas."""
    from sprint_mas.metrics_collector import (
        LangSmithMetricsSuiteReport,
        ModelScenarioMetric,
        export_metrics_artifacts,
    )

    report = LangSmithMetricsSuiteReport(
        report_id="test-csv-02",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=2,
        metrics=[
            ModelScenarioMetric(
                model_name="openai/gpt-oss-120b",
                scenario="scenario_b",
                runs_count=1,
                mean_duration_ms=1500.0,
                median_duration_ms=1500.0,
                p95_duration_ms=1500.0,
                mean_prompt_tokens=120.0,
                mean_completion_tokens=60.0,
                mean_total_tokens=180.0,
                total_cost_usd=0.0015,
                success_rate_pct=100.0,
            ),
            ModelScenarioMetric(
                model_name="qwen/qwen3.8-27b",
                scenario="scenario_c",
                runs_count=1,
                mean_duration_ms=1200.0,
                median_duration_ms=1200.0,
                p95_duration_ms=1200.0,
                mean_prompt_tokens=80.0,
                mean_completion_tokens=40.0,
                mean_total_tokens=120.0,
                total_cost_usd=0.0005,
                success_rate_pct=100.0,
            ),
        ],
        all_passed=True,
        notes=[],
    )

    artifacts = export_metrics_artifacts(report, base_filename="csv_test", output_dir=tmp_path)
    csv_path = artifacts["csv"]

    raw_bytes = csv_path.read_bytes()
    assert b"\r\r\n" not in raw_bytes, "Detected prohibited CRCRLF sequence in exported CSV"

    lines = csv_path.read_text(encoding="utf-8").strip().split("\n")
    header_cols = len(lines[0].split(","))
    assert header_cols == 11
    for idx, line in enumerate(lines[1:], start=2):
        cols = len(line.split(","))
        assert cols == header_cols, f"Line {idx} has {cols} columns, expected {header_cols}"


def test_path_traversal_blocked(tmp_path: Path):
    """Caminhos com .. ou extensão não autorizada são barrados com ValueError."""
    from sprint_mas.metrics_collector import (
        LangSmithMetricsSuiteReport,
        export_metrics_artifacts,
    )

    report = LangSmithMetricsSuiteReport(
        report_id="test-sec-03",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=0,
        metrics=[],
        all_passed=True,
        notes=[],
    )

    with pytest.raises(ValueError, match="Security violation"):
        export_metrics_artifacts(
            report,
            base_filename="../../malicious_escape",
            output_dir=tmp_path,
        )


# ===========================================================================
# 4. Verificação Reflexiva de Hardening Pydantic v2
# ===========================================================================


def test_verify_pydantic_hardening_includes_metrics_models():
    """verify_pydantic_models_hardening inclui ModelScenarioMetric e LangSmithMetricsSuiteReport e passa 100%."""
    probe_result = verify_pydantic_models_hardening()
    assert probe_result.passed is True
    assert probe_result.status == "PASSED"
    assert "ConfigDict(extra='forbid')" in probe_result.details


# ===========================================================================
# 5. Integração com a CLI (main.py --sync-metrics / --pull-langsmith)
# ===========================================================================


def test_cli_sync_metrics_success(capsys):
    """main.py --sync-metrics executa pull_langsmith_metrics e retorna exit code 0."""
    from main import run_cli
    from sprint_mas.metrics_collector import (
        LangSmithMetricsSuiteReport,
        ModelScenarioMetric,
    )

    mock_report = LangSmithMetricsSuiteReport(
        report_id="cli-test-01",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=1,
        metrics=[
            ModelScenarioMetric(
                model_name="openai/gpt-oss-120b",
                scenario="scenario_b",
                runs_count=1,
                mean_duration_ms=1500.0,
                median_duration_ms=1500.0,
                p95_duration_ms=1500.0,
                mean_prompt_tokens=100.0,
                mean_completion_tokens=50.0,
                mean_total_tokens=150.0,
                total_cost_usd=0.001,
                success_rate_pct=100.0,
            )
        ],
        all_passed=True,
        notes=["CLI Test Passed"],
    )

    with patch("main.pull_langsmith_metrics", return_value=mock_report):
        code = run_cli(["--sync-metrics"])

    assert code == 0
    captured = capsys.readouterr()
    assert "LangSmith Multi-Model Empirical Metrics Summary" in captured.out
    assert "openai/gpt-oss-120b" in captured.out


def test_cli_pull_langsmith_alias_json_and_project(capsys):
    """main.py --pull-langsmith com --project e --json emite payload canônico e retorna exit code 0."""
    import json
    from main import run_cli
    from sprint_mas.metrics_collector import LangSmithMetricsSuiteReport

    mock_report = LangSmithMetricsSuiteReport(
        report_id="cli-test-json",
        project_name="Custom_LangSmith_Project",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=0,
        metrics=[],
        all_passed=True,
        notes=[],
    )

    with patch("main.pull_langsmith_metrics", return_value=mock_report) as mock_pull:
        code = run_cli(["--pull-langsmith", "--project", "Custom_LangSmith_Project", "--json"])

    mock_pull.assert_called_once_with(project_name="Custom_LangSmith_Project")
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["project_name"] == "Custom_LangSmith_Project"
    assert data["report_id"] == "cli-test-json"


def test_cli_sync_metrics_export_prefix(tmp_path):
    """main.py --sync-metrics com --export-prefix exporta artefatos quádruplos."""
    from main import run_cli
    from sprint_mas.metrics_collector import LangSmithMetricsSuiteReport

    mock_report = LangSmithMetricsSuiteReport(
        report_id="cli-test-exp",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=0,
        metrics=[],
        all_passed=True,
        notes=[],
    )

    prefix = "test_cli_metrics_export"
    with patch("main.pull_langsmith_metrics", return_value=mock_report):
        code = run_cli(["--sync-metrics", "--export-prefix", prefix])

    assert code == 0
    repo_root = Path(__file__).resolve().parent.parent
    exp_dir = repo_root / "reports" / "experiments"
    for ext in [".json", ".md", ".csv", ".tex"]:
        target = exp_dir / f"{prefix}{ext}"
        assert target.exists()
        # cleanup
        target.unlink(missing_ok=True)


def test_cli_sync_metrics_output_formats(tmp_path):
    """main.py --sync-metrics com --output salva no formato correspondente (.csv, .tex, .json)."""
    from main import run_cli
    from sprint_mas.metrics_collector import (
        LangSmithMetricsSuiteReport,
        ModelScenarioMetric,
    )

    mock_report = LangSmithMetricsSuiteReport(
        report_id="cli-test-out",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=1,
        metrics=[
            ModelScenarioMetric(
                model_name="openai/gpt-oss-120b",
                scenario="scenario_b",
                runs_count=1,
                mean_duration_ms=1500.0,
                median_duration_ms=1500.0,
                p95_duration_ms=1500.0,
                mean_prompt_tokens=100.0,
                mean_completion_tokens=50.0,
                mean_total_tokens=150.0,
                total_cost_usd=0.001,
                success_rate_pct=100.0,
            )
        ],
        all_passed=True,
        notes=[],
    )

    repo_root = Path(__file__).resolve().parent.parent
    rel_csv = Path("reports/experiments/temp_cli_out.csv")
    rel_tex = Path("reports/experiments/temp_cli_out.tex")

    try:
        with patch("main.pull_langsmith_metrics", return_value=mock_report):
            code_csv = run_cli(["--sync-metrics", "--output", str(rel_csv)])
            assert code_csv == 0
            assert (repo_root / rel_csv).exists()

            code_tex = run_cli(["--sync-metrics", "--output", str(rel_tex)])
            assert code_tex == 0
            assert (repo_root / rel_tex).exists()
    finally:
        (repo_root / rel_csv).unlink(missing_ok=True)
        (repo_root / rel_tex).unlink(missing_ok=True)


def test_cli_sync_metrics_path_traversal_blocked(capsys):
    """main.py --sync-metrics com --output hostil é bloqueado com exit code 1."""
    from main import run_cli

    code = run_cli(["--sync-metrics", "--output", "../../evil_escape.json"])
    assert code == 1
    captured = capsys.readouterr()
    assert "CLI Execution Error" in captured.err
    assert "Security violation" in captured.err


def test_cli_sync_metrics_failure_returns_2():
    """main.py --sync-metrics quando report.all_passed é False retorna exit code 2."""
    from main import run_cli
    from sprint_mas.metrics_collector import LangSmithMetricsSuiteReport

    mock_report = LangSmithMetricsSuiteReport(
        report_id="cli-test-fail",
        project_name="REIC_WESAAC_code",
        extracted_at="2026-11-06T12:00:00Z",
        total_runs_analyzed=0,
        metrics=[],
        all_passed=False,
        notes=["Rate limit exceeded HTTP 429"],
    )

    with patch("main.pull_langsmith_metrics", return_value=mock_report):
        code = run_cli(["--sync-metrics"])

    assert code == 2

