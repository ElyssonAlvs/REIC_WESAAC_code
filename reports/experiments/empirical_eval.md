# Relatório de Avaliação Empírica & Comparativo Humano

**Identificador do Relatório:** `empirical-eval-6c0922a1`  
**Data/Hora UTC:** `2026-11-07T02:46:19.449684+00:00`  
**Provedor / Modelo:** `offline` (`deterministic-fallback`)  
**Rastreabilidade Científica:** REIC 2026 (SBC) / WESAAC 2025 (UFC Quixadá)  

---

## 1. Confronto Científico de Desempenho e Confiabilidade (Seções 5 e 6)

| Cenário | M-Manual (ms) | M-Agente n8n (ms) | M-Agente LangGraph (ms) | Speedup (vs. Manual) | Redução Tempo (%) | Speedup (vs. n8n) | Taxa Sucesso LG | Taxa Sucesso n8n | Viabilidade Manual |
|---|---|---|---|---|---|---|---|---|---|
| `scenario_a` | -- | -- | 26.6 | -- | -- | -- | 100.0% | 100.0% | `LOW` |
| `scenario_b` | 765,000.0 | 4,200.0 | 29.9 | 25,551.10x | 100.00% | 140.28x | 100.0% | 100.0% | `HIGH_FATIGUE` |
| `scenario_c` | -- | -- | 61.4 | -- | -- | -- | 100.0% | 99.5% | `INFEASIBLE` |

---

## 2. Mitigação Qualitativa do Gargalo de Backend (Seção 6.3 - Cenário B)

> Resource Bottleneck Mitigation (REIC 2026, Section 6.3): Backend skill density is 63.33% (19/30 tasks). Fullstack developer dev_C (1.0 FTE) absorbed 3 backend task(s) (19 story points). Part-time specialist dev_D (0.5 FTE) allocated 10.0 pts against nominal ceiling of 10.0 pts (Capacity respected: True). Fullstack mitigation active: True.

| Métrica Analítica de Alocação | Valor Observado | Referência Teórica (REIC 2026) | Status de Validação |
|---|---|---|---|
| **Densidade de Backend** | `63.33%` (19/30 tarefas) | `63.33%` (19/30 tarefas) | ✅ Conforme |
| **Absorção por dev_C (Fullstack)** | `3` tarefas (`19` pts) | Mitigação ativa do gargalo | ✅ Mitigado |
| **Teto de dev_D (0.5 FTE)** | `10.0` pts (Teto: `10.0` pts) | `<= 10.0` story points | ✅ Respeitado |

---

## 3. Tabela Canônica para Publicação Científica (LaTeX Booktabs)

```latex
\begin{table}[htbp]
\centering
\caption{Cross-Paradigm Empirical Evaluation: Human Manual vs. n8n Workflow vs. LangGraph BDI MAS}
\label{tab:empirical_evaluation}
\begin{tabular}{lrrrrrrr}
\toprule
\textbf{Scenario} & \textbf{Manual (ms)} & \textbf{n8n (ms)} & \textbf{LangGraph (ms)} & \textbf{Speedup (vs Man.)} & \textbf{Time Red. (\%)} & \textbf{Speedup (vs n8n)} & \textbf{Success (\%)} \\
\midrule
Scenario\_A & -- & -- & 26.6 & -- & -- & -- & 100.0\% \\
Scenario\_B & 765,000.0 & 4,200.0 & 29.9 & 25,551.10x & 100.00\% & 140.28x & 100.0\% \\
Scenario\_C & -- & -- & 61.4 & -- & -- & -- & 100.0\% \\
\bottomrule
\end{tabular}
\end{table}
```

**Confiabilidade em Escala (Cenário C):** `LangGraph BDI 100.0% vs. n8n 99.5% vs. Manual Infeasibility`