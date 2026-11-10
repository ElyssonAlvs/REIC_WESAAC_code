"""Automated Scientific Replication Engine and Publication Bundle Exporter (sprint_mas/replication.py).

Provides deterministic 1-click execution of the entire experimental pipeline:
1. Multi-scenario benchmark suite (Scenarios A, B, and C)
2. Empirical evaluation against human baseline and legacy n8n (REIC 2026 / WESAAC 2025)
3. Expanded Pentagon Defense security and semantic audit
4. Multi-format artifact generation (JSON, Markdown, LaTeX booktabs, CSV)
with anti-path traversal protections and strict Pydantic v2 validation (extra='forbid').
"""

from contextlib import nullcontext
import csv
from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Any, Optional, Union
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sprint_mas.benchmarks import (
    BenchmarkConfig,
    BenchmarkSuiteReport,
    normalize_scenario_name,
    run_benchmark_suite,
    temporary_offline_tracing,
    validate_safe_benchmark_path,
)
from sprint_mas.evaluation import (
    EmpiricalEvaluationReport,
    format_empirical_evaluation_latex,
    run_empirical_evaluation,
)
from sprint_mas.security_audit import (
    SecuritySemanticAuditReport,
    run_pentagon_security_audit,
)


class ReplicationPackageConfig(BaseModel):
    """Immutable execution configuration for the scientific replication package."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[str] = Field(
        default=["scenario_a", "scenario_b", "scenario_c"],
        description="List of canonical or aliased scenario names to replicate.",
    )
    runs: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Number of benchmark repetitions per scenario (1 to 50).",
    )
    offline_mock: bool = Field(
        default=True,
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
    strict: bool = Field(
        default=False,
        description="Strict validation mode without deterministic agent fallbacks.",
    )
    enable_scope_trimming: bool = Field(
        default=True,
        description="Whether to perform capacity-based scope trimming during corrective replanning.",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional LLM provider identifier ('groq', 'ollama', or 'offline').",
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional specific LLM model identifier.",
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


class ScientificReplicationBundle(BaseModel):
    """Consolidated scientific replication bundle encapsulating benchmarks, empirical evaluation, and security audit."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str = Field(..., description="Unique replication execution UUID.")
    reproduced_at: str = Field(..., description="ISO 8601 UTC timestamp of replication execution.")
    config: ReplicationPackageConfig = Field(..., description="Configuration parameters used for replication.")
    benchmark_report: BenchmarkSuiteReport = Field(..., description="Multi-scenario benchmark suite execution report.")
    empirical_report: EmpiricalEvaluationReport = Field(..., description="Empirical comparison against human and n8n baselines.")
    security_report: SecuritySemanticAuditReport = Field(..., description="Pentagon Defense security and semantic audit report.")
    is_fully_reproduced: bool = Field(
        ...,
        description="True if all benchmarks passed, all security probes passed, and Section 6.3 bottleneck was mitigated.",
    )
    bottleneck_mitigated: bool = Field(
        ...,
        description="True if Section 6.3 backend bottleneck was mitigated by fullstack dev_C with dev_D <= 10.0 pts.",
    )
    summary_notes: list[str] = Field(default_factory=list, description="Diagnostic and scientific reproduction notes.")
    provider: str = Field(..., description="Active LLM provider or offline fallback indicator.")
    model_name: str = Field(..., description="Active LLM model identifier.")


def run_scientific_replication(
    config: Optional[ReplicationPackageConfig] = None,
) -> ScientificReplicationBundle:
    """Orchestrates end-to-end scientific replication of experimental results for WESAAC 2025 and REIC 2026.

    Executes in sequence:
    1. Multi-scenario benchmark suite (Phase 9)
    2. Empirical cross-paradigm evaluation against human baseline (Phase 10)
    3. Pentagon Defense security audit and semantic verification (Phase 11)

    Args:
        config: Optional ReplicationPackageConfig. If None, default configuration is used.

    Returns:
        ScientificReplicationBundle: Consolidated replication bundle with audit verdict.
    """
    cfg = config or ReplicationPackageConfig()

    bench_config = BenchmarkConfig(
        scenarios=cfg.scenarios,
        runs=cfg.runs,
        provider=cfg.provider,
        model=cfg.model,
        offline_mock=cfg.offline_mock,
        max_retries=cfg.max_retries,
        sprint_days=cfg.sprint_days,
        points_per_day=cfg.points_per_day,
        enable_scope_trimming=cfg.enable_scope_trimming,
        strict=cfg.strict,
    )

    # Stage 1: Benchmark Suite Execution
    tracing_ctx = temporary_offline_tracing() if cfg.offline_mock else nullcontext()
    with tracing_ctx:
        benchmark_report = run_benchmark_suite(config=bench_config)

        # Stage 2: Empirical Evaluation & Baseline Confrontation
        empirical_report = run_empirical_evaluation(
            config=bench_config,
            suite_report=benchmark_report,
        )

        # Stage 3: Pentagon Defense Security & Semantic Verification
        security_report = run_pentagon_security_audit()

    # Integrity & Scientific Reproduction Verification
    all_benchmarks_passed = benchmark_report.all_approved
    all_security_passed = security_report.all_passed

    # Verify Section 6.3 Bottleneck Mitigation in Scenario B (if present)
    b_comp = next((c for c in empirical_report.comparisons if c.scenario == "scenario_b"), None)
    bottleneck_mitigated = False
    if b_comp and b_comp.bottleneck_analysis:
        bottleneck_mitigated = (
            b_comp.bottleneck_analysis.dev_d_capacity_respected
            and b_comp.bottleneck_analysis.fullstack_mitigation_active
        )
    elif not any(c.scenario == "scenario_b" for c in empirical_report.comparisons):
        # Scenario B not evaluated in this specific run
        bottleneck_mitigated = True

    is_fully_reproduced = (
        all_benchmarks_passed
        and all_security_passed
        and bottleneck_mitigated
    )

    speedup_b_desc = (
        f"{empirical_report.total_speedup_scenario_b:,.2f}x vs. Manual"
        if empirical_report.total_speedup_scenario_b is not None
        else "N/A"
    )

    summary_notes = [
        f"Stage 1: Multi-Scenario Benchmark Suite -> {'PASSED (100% approved)' if all_benchmarks_passed else 'FAILED'}.",
        f"Stage 2: Empirical Evaluation (REIC 2026 / WESAAC 2025) -> Speedup Scenario B: {speedup_b_desc}; Bottleneck Mitigated: {bottleneck_mitigated}.",
        f"Stage 3: Pentagon Defense Security Audit -> {'PASSED (0 violations)' if all_security_passed else 'FAILED'}.",
        f"Overall Scientific Reproduction Verdict -> {'FULLY REPRODUCED' if is_fully_reproduced else 'REPRODUCTION ANOMALY DETECTED'}.",
    ]

    bundle_id = f"replication-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    return ScientificReplicationBundle(
        bundle_id=bundle_id,
        reproduced_at=now_iso,
        config=cfg,
        benchmark_report=benchmark_report,
        empirical_report=empirical_report,
        security_report=security_report,
        is_fully_reproduced=is_fully_reproduced,
        bottleneck_mitigated=bottleneck_mitigated,
        summary_notes=summary_notes,
        provider=benchmark_report.provider,
        model_name=benchmark_report.model,
    )


def format_replication_markdown(bundle: ScientificReplicationBundle) -> str:
    """Formats ScientificReplicationBundle into an executive scientific report in Markdown."""
    status_label = "REPRODUCED (100% COMPLIANT)" if bundle.is_fully_reproduced else "REPRODUCTION FAILED"
    badge = f"**STATUS:** `{status_label}`"

    lines: list[str] = [
        "# Pacote de Reprodutibilidade Científica — WESAAC 2025 & REIC 2026",
        "",
        f"{badge}  ",
        f"**Identificador do Bundle:** `{bundle.bundle_id}`  ",
        f"**Data/Hora UTC:** `{bundle.reproduced_at}`  ",
        f"**Provedor / Modelo:** `{bundle.provider}` (`{bundle.model_name}`)  ",
        f"**Execução Offline Mock:** `{'Sim' if bundle.config.offline_mock else 'Não (Inferência Real LLM)'}`  ",
        f"**Cenários Avaliados:** {', '.join(f'`{s}`' for s in bundle.config.scenarios)}  ",
        f"**Repetições por Cenário (Runs):** {bundle.config.runs}  ",
        "",
        "---",
        "",
        "## 1. Sumário Executivo da Reprodução Experimental",
        "",
    ]

    for note in bundle.summary_notes:
        lines.append(f"- {note}")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Bateria de Benchmarks Automatizados (LangGraph BDI)",
        "",
        "| Cenário | Runs | Taxa Aprovação | Tempo Médio (ms) | P95 (ms) | Violações DAG | Violações FTE | Violações Skill | Replan Rate |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for s in bundle.benchmark_report.summaries:
        lines.append(
            f"| `{s.scenario}` | {s.total_runs} | {s.approval_rate * 100:.1f}% | {s.mean_time_ms:,.2f} | "
            f"{s.p95_time_ms:,.2f} | {s.dag_violations_total} | {s.fte_violations_total} | "
            f"{s.skill_violations_total} | {s.replan_rate * 100:.1f}% |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Avaliação Empírica Cruzada & Confronto com Linhas de Base",
        "",
        "| Cenário | Manual (ms) | n8n (ms) | LangGraph BDI (ms) | Speedup vs. Manual | Speedup vs. n8n | Redução Tempo (%) | Viabilidade Manual |",
        "|---|---|---|---|---|---|---|---|",
    ])

    for c in bundle.empirical_report.comparisons:
        man_str = f"{c.manual_time_ms:,.1f}" if c.manual_time_ms is not None else "N/A"
        n8n_str = f"{c.n8n_agent_time_ms:,.1f}" if c.n8n_agent_time_ms is not None else "N/A"
        lg_str = f"{c.langgraph_time_ms:,.2f}"
        sp_man = f"{c.speedup_vs_manual:,.2f}x" if c.speedup_vs_manual is not None else "N/A"
        sp_n8n = f"{c.speedup_vs_n8n:,.2f}x" if c.speedup_vs_n8n is not None else "N/A"
        red_man = f"{c.time_reduction_vs_manual_pct:,.2f}%" if c.time_reduction_vs_manual_pct is not None else "N/A"

        lines.append(
            f"| `{c.scenario}` | {man_str} | {n8n_str} | {lg_str} | {sp_man} | {sp_n8n} | {red_man} | `{c.manual_feasibility}` |"
        )

    b_comp = next((c for c in bundle.empirical_report.comparisons if c.scenario == "scenario_b"), None)
    if b_comp and b_comp.bottleneck_analysis:
        ba = b_comp.bottleneck_analysis
        lines.extend([
            "",
            "### Validação da Mitigação do Gargalo (Seção 6.3 - Cenário B)",
            f"- **Densidade de Backend:** {ba.backend_density_pct:.2f}% ({ba.backend_tasks_count}/{ba.total_tasks} tarefas)",
            f"- **Absorção por `dev_C` (Fullstack):** {ba.dev_c_backend_tasks_absorbed} tarefas ({ba.dev_c_backend_points_absorbed} story points)",
            f"- **Carga alocada a `dev_D` (0.5 FTE):** {ba.dev_d_allocated_points:.1f} pts (Teto nominal: {ba.dev_d_capacity_ceiling:.1f} pts)",
            f"- **Teto respeitado:** {'SIM (Conforme)' if ba.dev_d_capacity_respected else 'NÃO (Violação)'}",
        ])

    lines.extend([
        "",
        "---",
        "",
        "## 4. Auditoria de Segurança do Pentágono & Integridade Semântica",
        "",
        f"**Status Global de Segurança:** `{'PASSED' if bundle.security_report.all_passed else 'FAILED'}`  ",
        f"**Sondas Executadas:** {len(bundle.security_report.probes)} | **Verificações Semânticas:** {len(bundle.security_report.semantic_checks)}  ",
        "",
        "| Sonda / Verificação | Pilar / Módulo | Status | Latência (ms) | Detalhes |",
        "|---|---|---|---|---|",
    ])

    for p in bundle.security_report.probes:
        lines.append(f"| `{p.probe_id}` | {p.pilar} | `{p.status}` | {p.latency_ms:.3f} | {p.details} |")

    for s in bundle.security_report.semantic_checks:
        status_s = "PASSED" if s.passed else "FAILED"
        lines.append(f"| `semantic_check` | {s.module} | `{status_s}` | -- | {s.details} |")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Tabela Canônica para Publicação Acadêmica (LaTeX Booktabs)",
        "",
        "```latex",
        format_replication_latex(bundle),
        "```",
        "",
        "---",
        "*Pacote de Reprodutibilidade gerado deterministicamente pelo Sprint Planning MAS (REIC 2026 / WESAAC 2025).*",
    ])

    return "\n".join(lines)


def format_replication_latex(bundle: ScientificReplicationBundle) -> str:
    """Formats ScientificReplicationBundle into a publication-ready LaTeX booktabs table."""
    return format_empirical_evaluation_latex(bundle.empirical_report)


def format_replication_csv(bundle: ScientificReplicationBundle) -> str:
    """Formats ScientificReplicationBundle into a clean, canonical CSV spreadsheet."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    writer.writerow([
        "bundle_id",
        "timestamp",
        "scenario",
        "provider",
        "model_name",
        "langgraph_time_ms",
        "manual_time_ms",
        "n8n_agent_time_ms",
        "speedup_vs_manual",
        "time_reduction_vs_manual_pct",
        "speedup_vs_n8n",
        "langgraph_dag_violations",
        "langgraph_fte_violations",
        "dev_c_backend_absorbed_pts",
        "dev_d_allocated_pts",
        "dev_d_capacity_respected",
        "benchmarks_approved",
        "security_passed",
        "fully_reproduced",
    ])

    for c in bundle.empirical_report.comparisons:
        b_summary = next((s for s in bundle.benchmark_report.summaries if s.scenario == c.scenario), None)
        dag_viols = b_summary.dag_violations_total if b_summary else c.langgraph_dag_violations
        fte_viols = b_summary.fte_violations_total if b_summary else 0

        dev_c_pts = (
            str(c.bottleneck_analysis.dev_c_backend_points_absorbed)
            if c.bottleneck_analysis is not None
            else "N/A"
        )
        dev_d_pts = (
            str(c.bottleneck_analysis.dev_d_allocated_points)
            if c.bottleneck_analysis is not None
            else "N/A"
        )
        dev_d_resp = (
            str(c.bottleneck_analysis.dev_d_capacity_respected)
            if c.bottleneck_analysis is not None
            else "N/A"
        )

        man_ms = str(c.manual_time_ms) if c.manual_time_ms is not None else "N/A"
        n8n_ms = str(c.n8n_agent_time_ms) if c.n8n_agent_time_ms is not None else "N/A"
        sp_man = str(c.speedup_vs_manual) if c.speedup_vs_manual is not None else "N/A"
        red_man = str(c.time_reduction_vs_manual_pct) if c.time_reduction_vs_manual_pct is not None else "N/A"
        sp_n8n = str(c.speedup_vs_n8n) if c.speedup_vs_n8n is not None else "N/A"

        writer.writerow([
            bundle.bundle_id,
            bundle.reproduced_at,
            c.scenario,
            bundle.provider,
            bundle.model_name,
            c.langgraph_time_ms,
            man_ms,
            n8n_ms,
            sp_man,
            red_man,
            sp_n8n,
            dag_viols,
            fte_viols,
            dev_c_pts,
            dev_d_pts,
            dev_d_resp,
            bundle.benchmark_report.all_approved,
            bundle.security_report.all_passed,
            bundle.is_fully_reproduced,
        ])

    return output.getvalue()


def export_replication_artifacts(
    bundle: ScientificReplicationBundle,
    base_filename: str = "replication_bundle",
    output_dir: Optional[Union[str, Path]] = None,
    export_json: bool = True,
    export_md: bool = True,
    export_csv: bool = True,
    export_tex: bool = True,
) -> dict[str, Path]:
    """Safely exports scientific replication artifacts in .json, .md, .csv, and .tex formats.

    Args:
        bundle: ScientificReplicationBundle instance to export.
        base_filename: Base filename without extension (default: 'replication_bundle').
        output_dir: Directory relative to repository root or absolute Path.
        export_json: Whether to export canonical JSON.
        export_md: Whether to export executive Markdown report.
        export_csv: Whether to export clean tabular CSV.
        export_tex: Whether to export LaTeX booktabs table.

    Returns:
        dict[str, Path]: Map of format identifier ('json', 'md', 'csv', 'tex') to written Path.

    Raises:
        ValueError: If base_filename or output_dir contains directory traversal patterns or bad extensions.
    """
    if not base_filename or not str(base_filename).strip():
        raise ValueError("Security violation: base_filename cannot be empty.")

    raw_base = Path(base_filename)
    if ".." in raw_base.parts:
        raise ValueError(f"Security violation: path traversal detected in base_filename '{base_filename}'.")

    if raw_base.suffix and raw_base.suffix.lower() not in {".json", ".md", ".csv", ".tex"}:
        raise ValueError(
            f"Security violation: forbidden extension in base_filename '{raw_base.suffix}'. Allowed: .json, .md, .csv, .tex"
        )

    repo_root = Path(__file__).resolve().parent.parent.resolve()

    if output_dir is not None:
        if not str(output_dir).strip():
            raise ValueError("Security violation: output_dir cannot be empty.")
        raw_out = Path(output_dir)
        if ".." in raw_out.parts:
            raise ValueError(f"Security violation: path traversal detected in output_dir '{output_dir}'.")
        if raw_out.suffix and raw_out.suffix.lower() not in {".json", ".md", ".csv", ".tex"}:
            raise ValueError(f"Security violation: forbidden extension in output_dir '{raw_out.suffix}'.")
        if raw_out.is_absolute():
            out_dir_path = raw_out.resolve()
        else:
            out_dir_path = (repo_root / raw_out).resolve()
    else:
        out_dir_path = None

    clean_base = str(base_filename).strip()
    for sfx in [".json", ".md", ".csv", ".tex"]:
        if clean_base.lower().endswith(sfx):
            clean_base = clean_base[:-len(sfx)]

    def _resolve_target(ext: str) -> Path:
        if out_dir_path is not None:
            candidate = out_dir_path / f"{Path(clean_base).name}{ext}"
        else:
            base_p = Path(clean_base)
            if base_p.is_absolute():
                candidate = Path(f"{clean_base}{ext}")
            elif len(base_p.parts) > 1:
                candidate = repo_root / f"{clean_base}{ext}"
            else:
                candidate = repo_root / "reports" / "experiments" / "replication" / f"{clean_base}{ext}"

        safe_path = validate_safe_benchmark_path(candidate, base_dir=repo_root)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        return safe_path

    artifacts: dict[str, Path] = {}

    if export_json:
        target_json = _resolve_target(".json")
        target_json.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        artifacts["json"] = target_json

    if export_md:
        target_md = _resolve_target(".md")
        target_md.write_text(format_replication_markdown(bundle), encoding="utf-8")
        artifacts["md"] = target_md

    if export_csv:
        target_csv = _resolve_target(".csv")
        target_csv.write_text(format_replication_csv(bundle), encoding="utf-8", newline="")
        artifacts["csv"] = target_csv

    if export_tex:
        target_tex = _resolve_target(".tex")
        target_tex.write_text(format_replication_latex(bundle), encoding="utf-8")
        artifacts["tex"] = target_tex

    return artifacts
