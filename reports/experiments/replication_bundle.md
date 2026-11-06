# Pacote de Reprodutibilidade Científica — WESAAC 2025 & REIC 2026

**STATUS:** `REPRODUCED (100% COMPLIANT)`  
**Identificador do Bundle:** `replication-22a5ae1b`  
**Data/Hora UTC:** `2026-11-06T22:22:15.280999+00:00`  
**Provedor / Modelo:** `offline` (`deterministic-fallback`)  
**Execução Offline Mock:** `Sim`  
**Cenários Avaliados:** `scenario_a`, `scenario_b`, `scenario_c`  
**Repetições por Cenário (Runs):** 1  

---

## 1. Sumário Executivo da Reprodução Experimental

- Stage 1: Multi-Scenario Benchmark Suite -> PASSED (100% approved).
- Stage 2: Empirical Evaluation (REIC 2026 / WESAAC 2025) -> Speedup Scenario B: 27,060.49x vs. Manual; Bottleneck Mitigated: True.
- Stage 3: Pentagon Defense Security Audit -> PASSED (0 violations).
- Overall Scientific Reproduction Verdict -> FULLY REPRODUCED.

---

## 2. Bateria de Benchmarks Automatizados (LangGraph BDI)

| Cenário | Runs | Taxa Aprovação | Tempo Médio (ms) | P95 (ms) | Violações DAG | Violações FTE | Violações Skill | Replan Rate |
|---|---|---|---|---|---|---|---|---|
| `scenario_a` | 1 | 100.0% | 18.49 | 18.49 | 0 | 0 | 0 | 0.0% |
| `scenario_b` | 1 | 100.0% | 28.27 | 28.27 | 0 | 0 | 0 | 100.0% |
| `scenario_c` | 1 | 100.0% | 59.17 | 59.17 | 0 | 0 | 0 | 100.0% |

---

## 3. Avaliação Empírica Cruzada & Confronto com Linhas de Base

| Cenário | Manual (ms) | n8n (ms) | LangGraph BDI (ms) | Speedup vs. Manual | Speedup vs. n8n | Redução Tempo (%) | Viabilidade Manual |
|---|---|---|---|---|---|---|---|
| `scenario_a` | N/A | N/A | 18.49 | N/A | N/A | N/A | `LOW` |
| `scenario_b` | 765,000.0 | 4,200.0 | 28.27 | 27,060.49x | 148.57x | 100.00% | `HIGH_FATIGUE` |
| `scenario_c` | N/A | N/A | 59.17 | N/A | N/A | N/A | `INFEASIBLE` |

### Validação da Mitigação do Gargalo (Seção 6.3 - Cenário B)
- **Densidade de Backend:** 63.33% (19/30 tarefas)
- **Absorção por `dev_C` (Fullstack):** 3 tarefas (19 story points)
- **Carga alocada a `dev_D` (0.5 FTE):** 10.0 pts (Teto nominal: 10.0 pts)
- **Teto respeitado:** SIM (Conforme)

---

## 4. Auditoria de Segurança do Pentágono & Integridade Semântica

**Status Global de Segurança:** `PASSED`  
**Sondas Executadas:** 6 | **Verificações Semânticas:** 2  

| Sonda / Verificação | Pilar / Módulo | Status | Latência (ms) | Detalhes |
|---|---|---|---|---|
| `probe_pydantic_hardening` | Pilar 5: Segredos, Inputs & Parsers Seguros | `PASSED` | 0.022 | Verified 23 domain Pydantic models. 100% enforce ConfigDict(extra='forbid'). |
| `probe_session_isolation` | Pilar 1: Isolamento de Sessão & Estado | `PASSED` | 6.003 | MemorySaver checkpoint state for thread_alpha and thread_beta verified. Zero cross-thread pollution. |
| `probe_server_authority` | Pilar 2: Zero Confiança no Cliente / LLM (Server Authority) | `PASSED` | 1.498 | Server Authority strictly enforced: hostile approval rejected and prompt injection directive blocked. |
| `probe_anti_idor` | Pilar 3: Anti-IDOR Sistemático | `PASSED` | 0.818 | Anti-IDOR verified: ghost_dev and TSK-999 blocked across deterministic tools and state validator. |
| `probe_dos_iterative_dag` | Pilar 4: Concorrência, Idempotência & Anti-DoS | `PASSED` | 6.567 | Iterative DFS validated on 1500 linear nodes in 6.6ms without RecursionError. Deep cycle successfully detected. |
| `probe_path_traversal` | Pilar 5: Segredos, Inputs & Parsers Seguros | `PASSED` | 0.698 | Path traversal immunity verified: 6/6 adversarial attacks blocked. |
| `semantic_check` | evals.golden_dataset | `PASSED` | -- | Golden datasets A (35 pts, 10 tasks) and B (66 pts, 15 tasks) validated. Zero audit violations. |
| `semantic_check` | configs.prompts.bart_templates | `PASSED` | -- | BART prompt templates and scenarios A/B/C topological DAGs semantically verified. |

---

## 5. Tabela Canônica para Publicação Acadêmica (LaTeX Booktabs)

```latex
\begin{table}[htbp]
\centering
\caption{Cross-Paradigm Empirical Evaluation: Human Manual vs. n8n Workflow vs. LangGraph BDI MAS}
\label{tab:empirical_evaluation}
\begin{tabular}{lrrrrrrr}
\toprule
\textbf{Scenario} & \textbf{Manual (ms)} & \textbf{n8n (ms)} & \textbf{LangGraph (ms)} & \textbf{Speedup (vs Man.)} & \textbf{Time Red. (\%)} & \textbf{Speedup (vs n8n)} & \textbf{Success (\%)} \\
\midrule
Scenario\_A & -- & -- & 18.5 & -- & -- & -- & 100.0\% \\
Scenario\_B & 765,000.0 & 4,200.0 & 28.3 & 27,060.49x & 100.00\% & 148.57x & 100.0\% \\
Scenario\_C & -- & -- & 59.2 & -- & -- & -- & 100.0\% \\
\bottomrule
\end{tabular}
\end{table}
```

---
*Pacote de Reprodutibilidade gerado deterministicamente pelo Sprint Planning MAS (REIC 2026 / WESAAC 2025).*