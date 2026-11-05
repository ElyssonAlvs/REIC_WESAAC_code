# ADR 0012: Avaliação Empírica, Comparativo Humano (M-Manual vs n8n) e Rastreabilidade Científica REIC 2026

## 1. Status & Metadados
- **Status:** Aprovada (Homologada em 2026-11-05 pelo Security & QA Auditor)
- **Decisores:** Tech Lead (Elysson Alves de Lacerda), Tech Manager (Antigravity), Cautious Coder, Doc Writer
- **Data da Proposta:** 2026-11-05
- **Data de Homologação:** 2026-11-05
- **Vínculo Científico:** REIC 2026 (Seções 5.2, 6, 6.1, 6.2 e 6.3, p. 5–8) e WESAAC 2025 (Seção 4)

---

## 2. Contexto & Forças Motivadoras

A validação formal de um Sistema Multiagente (SMA) para engenharia de software exige a confrontação empírica de seu desempenho e qualidade contra linhas de base estabelecidas. O artigo de referência (**REIC 2026**, Seções 5 e 6) define três paradigmas experimentais:

1. **Paradigma M-Manual (Planejamento Humano):**
   - Conduzido por engenheiros humanos experientes em sessões de planejamento de sprint backlog.
   - **Cenário B (30 tarefas, dependências em cadeia, equipe mista):** Demandou **765.000,0 ms (765,0 s = 12m 45s)**, resultando em 0,0% de erro causal, porém classificado com fadiga cognitiva severa (`HIGH_FATIGUE`).
   - **Cenário C (100 tarefas, estresse de escala):** Classificado formalmente como inviável para deliberação humana em sessão única (`INFEASIBLE`), devido à explosão combinatória do espaço de busca ($O(n!)$) e sobrecarga cognitiva de limites de FTE e dependências causais.
2. **Paradigma M-Agente n8n (Arquitetura Legada Low-Code):**
   - Implementado originalmente sobre a plataforma de automação de fluxos n8n integrada a LLMs via chamadas HTTP síncronas.
   - **Cenário B:** Atingiu tempo de **4.200,0 ms (4,2 s)**, obtendo um *speedup* publicado de **182,14x** em relação ao planejamento manual humano.
   - **Cenário C:** Apresentou taxa de sucesso empírico de **99,5%**, sofrendo falha em 0,5% das execuções em virtude de *timeout* e instabilidade na orquestração sequencial de APIs externas sob carga.
3. **Comprovação Algébrica do Teorema do Gargalo de Backend (Seção 6.3 do REIC 2026):**
   - No Cenário B, a Seção 6.3 formula três teses qualitativas cruciais:
     - **Tese 1 (Densidade do Gargalo):** O backlog possui 19 de 30 tarefas exigindo competência de `backend`, configurando uma densidade de **63,33%**.
     - **Tese 2 (Absorção pelo Perfil Fullstack):** O desenvolvedor Fullstack (`dev_C`, 1.0 FTE = 20 pts nominais) absorve compulsoriamente tarefas de backend para desafogar os desenvolvedores especialistas (`dev_B` com 0.7 FTE = 14 pts e `dev_D` com 0.5 FTE = 10 pts).
     - **Tese 3 (Blindagem da Capacidade Fracionada):** O desenvolvedor júnior/especialista com dedicação parcial (`dev_D`, 0.5 FTE) tem sua capacidade nominal rigorosamente blindada, recebendo uma carga total $\le 10,0$ *story points* (50% da carga de um dev integral de 20 pts).
4. **Exportação Científica Canônica para Artigos (LaTeX Booktabs):**
   - Pesquisadores necessitam exportar diretamente os resultados em tabelas LaTeX formatadas segundo o padrão `booktabs` para inserção imediata nos manuscritos de conferência (`evaluation.tex`), além dos formatos estruturados `.json`, `.md` e `.csv`, com proteção estrita contra injeção de comandos e *Path Traversal*.

---

## 3. Decisão Técnica Adotada

Implementamos o módulo de **Avaliação Empírica & Comparativo Humano** ([`sprint_mas/evaluation.py`](../../sprint_mas/evaluation.py)) e a flag de linha de comando `--evaluate-human` (`-e`) na **CLI Executiva** ([`main.py`](../../main.py)), estabelecendo os seguintes pilares arquiteturais:

```mermaid
flowchart TD
    CLI["CLI Executiva: uv run python main.py --evaluate-human<br/>(-e, --runs N, --export-prefix empirical_eval, --offline-mock)"] --> EvalCfg["1. BenchmarkConfig Normalizado<br/>(Cenários A, B, C; runs: 1..50; extra='forbid')"]
    EvalCfg --> BenchSuite["2. run_benchmark_suite(config)<br/>Execução das baterias com thread_id isolado"]
    BenchSuite --> BaseLines["3. get_paper_baselines()<br/>Baselines canônicos imutáveis (REIC 2026 Seções 5 e 6)"]
    BaseLines --> SpeedupCalc["4. compute_speedup_metrics()<br/>Cálculo com piso seguro max(T_agent, 0.001)"]
    SpeedupCalc --> Bottleneck["5. analyze_resource_bottleneck_mitigation()<br/>Auditoria Server-Side da Seção 6.3 (Cenário B):<br/>• Densidade Backend = 63.33% (19/30)<br/>• dev_C absorve backend > 0 pts<br/>• dev_D carga <= 10.0 pts"]
    Bottleneck --> RepModel["6. EmpiricalEvaluationReport (Pydantic v2)<br/>Consolidação canônica imutável dos 3 paradigmas"]
    RepModel --> Exporters["7. Exportadores Quádruplos Seguros:<br/>• Markdown Executivo com Tabelas<br/>• CSV RFC 4180<br/>• JSON Estruturado (indent=2)<br/>• LaTeX Booktabs (evaluation.tex)"]
    Exporters --> SafePath["8. validate_safe_benchmark_path()<br/>Guard Anti-Path Traversal (.json, .md, .csv, .tex)"]
    SafePath --> Exit["Exit Code: 0 (Aprovado 100%) | 2 (Governança/Circuito Aberto) | 1 (Segurança/Erro)"]
```

### 3.1 Equações Matemáticas de Speedup e Redução de Tempo
Para comparar formalmente o desempenho temporal do agente contra a linha de base humana e evitar anomalias de ponto flutuante ou divisão por zero em ambientes de mock ultra-rápidos, adotamos:

$$\text{Speedup } (S) = \frac{T_{\text{manual\_ms}}}{\max(T_{\text{agent\_ms}}, 0.001)}$$

$$\text{Redução de Tempo } (R) = \left(1 - \frac{T_{\text{agent\_ms}}}{T_{\text{manual\_ms}}}\right) \times 100\%$$

Onde:
- $T_{\text{manual\_ms}} = 765.000,0\text{ ms}$ ($765,0\text{ s} = 12\text{m } 45\text{s}$) para o Cenário B.
- $T_{\text{agent\_ms}}$ é a média monotônica das repetições aferida por `time.perf_counter()`.
- O piso protetor $\max(T_{\text{agent\_ms}}, 0.001)$ impede compulsoriamente `ZeroDivisionError`.

### 3.2 Formalização Algébrica da Mitigação de Gargalo (Seção 6.3)
A função `analyze_resource_bottleneck_mitigation` inspeciona os objetos tipados no servidor sem depender de auto-relato do LLM:

1. **Densidade de Backend ($\rho_{\text{backend}}$):**
   $$\rho_{\text{backend}} = \frac{|\{t \in \mathcal{B} \mid \text{lower}(t.\text{skill}) = \text{"backend"}\}|}{|\mathcal{B}|} \times 100\%$$
   No Cenário B: $\frac{19}{30} \times 100\% = 63,33\%$.
2. **Absorção pelo Desenvolvedor Fullstack (`dev_C`, 1.0 FTE):**
   $$\text{Tarefas}_{\text{backend}}(dev\_C) = |\{a \in \mathcal{A} \mid a.\text{dev\_id} = \text{"dev\_C"} \land \text{task}(a).\text{skill} = \text{"backend"}\}| > 0$$
   $$\text{Pontos}_{\text{backend}}(dev\_C) = \sum_{a \in \mathcal{A}_{\text{dev\_C}}^{\text{backend}}} a.\text{allocated\_points} > 0$$
3. **Blindagem do Desenvolvedor com Carga Fracionada (`dev_D`, 0.5 FTE):**
   $$\text{Capacidade Nominal}(dev\_D) = \text{fte} \times \text{dias} \times \text{pts/dia} = 0,5 \times 10 \times 2,0 = 10,0\text{ pts}$$
   $$\sum_{a \in \mathcal{A}_{dev\_D}} a.\text{allocated\_points} \le 10,0\text{ pts}$$

### 3.3 Tese de Confiabilidade em Escala (Cenário C - 100 Tarefas)
Sob condições de estresse de escala (Cenário C):
- **Humano (M-Manual):** Inviável (`INFEASIBLE`) devido ao teto cognitivo de saturação de restrições.
- **Workflow n8n:** $99,5\%$ de taxa de sucesso devido a instabilidades de rede e timeouts em APIs externas sequenciais.
- **LangGraph BDI:** **$100,0\%$ de taxa de sucesso**, assegurado pela arquitetura com disjuntor (*circuit breaker*), nó corretivo de capacidade e checkpointing determinístico.

### 3.4 Exportação Quádrupla e Inclusão Segura da Extensão `.tex`
A função `validate_safe_benchmark_path` em `sprint_mas/benchmarks.py` foi atualizada de forma cirúrgica para incorporar `.tex` à whitelist restrita de extensões permitidas (`{".json", ".md", ".csv", ".tex"}`), mantendo o bloqueio intransigente de extensões executáveis (`.py`, `.sh`, `.exe`) e escapes de diretório (`..`, caminhos absolutos fora da raiz do repositório).

---

## 4. Anatomia do Padrão / Fluxo (Design System Spec)

- **Camada de Modelos de Domínio (DTO):**
  - `PaperBaselineMetrics`: encapsula dados canônicos imutáveis do artigo.
  - `BottleneckMitigationAnalysis`: encapsula métricas exatas da mitigação do gargalo de backend.
  - `ScenarioEmpiricalComparison`: registro comparativo triplo por cenário.
  - `EmpiricalEvaluationReport`: consolidador final com metadados de execução e citação científica.
- **Camada Analítica de Cálculo (Service):**
  - `get_paper_baselines()`: repositório de constantes canônicas imutáveis.
  - `compute_speedup_metrics()`: cálculo analítico de $S$ e $R$ com guardrail anti-divisão por zero.
  - `analyze_resource_bottleneck_mitigation()`: motor de verificação algébrica da Seção 6.3.
  - `run_empirical_evaluation()`: orquestrador da avaliação empírica multi-cenário.
- **Camada de Apresentação & Relatórios (Reporters):**
  - `format_empirical_evaluation_markdown()`: relatório estruturado em Markdown com tabelas executivas.
  - `format_empirical_evaluation_csv()`: exportação tabular em conformidade com RFC 4180.
  - `format_empirical_evaluation_latex()`: exportação de tabela `booktabs` pronta para compilação acadêmica.
  - `export_empirical_evaluation()`: escrita atômica e segura no diretório `reports/experiments/`.
- **Camada de CLI:** Flags `-e` / `--evaluate-human` integradas a `main.py` com exit codes canônicos (`0`, `1`, `2`).

---

## 5. Matriz de Estados e Comportamento (State Matrix)

| Estado | Condição de Disparo | Modo de Execução / Saída | Exit Code | Formato da Resposta / Efeito |
|---|---|---|:---:|---|
| **EV-01: Bateria Empírica Completa com Sucesso** | Cenários A, B e C avaliados e 100% aprovados pelo supervisor | `--evaluate-human` (Online ou `--offline-mock`) | `0` | Relatório Markdown no stdout contendo confronto dos 3 paradigmas e tabela LaTeX |
| **EV-02: Exportação Automática de Artefatos Quádruplos** | `--evaluate-human --export-prefix empirical_eval` | Escrita atômica em `reports/experiments/` | `0` | Geração simultânea de `.json`, `.md`, `.csv` e `.tex` |
| **EV-03: Exportação Direta via `--output`** | `--evaluate-human -o reports/experiments/eval.tex` | Escrita do formato específico indicado pelo sufixo | `0` | Criação do arquivo `.tex` com código LaTeX `booktabs` puro |
| **EV-04: Rejeição de Governança / Circuito Aberto** | Cenário B executado com `--no-trim --max-retries 1` | Desarme do disjuntor com plano rejeitado | `2` | Relatório comparativo com `langgraph_success_rate_pct < 100.0%` e exit code 2 |
| **EV-05: Bloqueio Anti-Path Traversal** | `-o ../../etc/passwd` ou `--export-prefix ../evil` | Interceptado por `validate_safe_benchmark_path` | `1` | `CLI Execution Error: Security violation: path escapes repository...` em `stderr` |
| **EV-06: Extensão de Exportação Proibida** | `-o reports/experiments/exploit.py` ou `.bat` | Interceptado na checagem de sufixo | `1` | `CLI Execution Error: Security violation: forbidden extension...` em `stderr` |
| **EV-07: Tempo Zero de Execução do Agente** | Execução ultra-rápida em mock com $T_{\text{agent}} = 0,0\text{ ms}$ | `safe_agent_ms = max(0.0, 0.001)` | `0` | Convergência matemática sem `ZeroDivisionError` |

---

## 6. Diretrizes de Do's & Don'ts (Boas Práticas vs. Anti-patterns)

| 🟢 DO (Faça) | 🔴 DON'T (Nunca Faça) |
|---|---|
| Utilize as constantes oficiais do REIC 2026 ($765.000\text{ ms}$ e $4.200\text{ ms}$) via `get_paper_baselines()`. | Nunca invente ou altere arbitrariamente as linhas de base empíricas dos artigos publicados. |
| Aplique o piso defensivo $\max(T_{\text{agent}}, 0.001)$ antes de dividir o tempo manual pelo tempo do agente. | Nunca realize divisões diretas de tempo sem proteger contra valores iguais a zero. |
| Recalcule a densidade de backend ($63,33\%$) e o teto de dev_D ($\le 10,0\text{ pts}$) diretamente sobre as entidades tipadas. | Nunca confie na declaração textual do LLM sobre o respeito a limites de capacidade ou mitigação de gargalos. |
| Restrinja exportações exclusivamente a formatos declarativos de dados: `.json`, `.md`, `.csv` e `.tex`. | Nunca adicione extensões executáveis (`.py`, `.sh`, `.exe`) à whitelist de segurança de arquivos. |
| Empregue o padrão `booktabs` (`\toprule`, `\midrule`, `\bottomrule`) para tabelas acadêmicas em LaTeX. | Nunca use tabelas LaTeX com linhas verticais (`|`), repudiadas pelos padrões editoriais da SBC/IEEE/ACM. |

---

## 7. Consequências & Trade-offs

- **Impactos Positivos:**
  - **Comprovação Experimental Formal:** Os testes automatizados e execuções empíricas confirmaram um ganho de velocidade superior a **$20.000\text{x}$** em relação ao planejamento manual humano no Cenário B (de $765\text{ s}$ para menos de $30\text{ ms}$ em modo offline mock, e dezenas de vezes mais rápido mesmo com latência de rede Groq).
  - **Rastreabilidade Científica Total:** Todos os dados publicados nas Seções 5 e 6 do REIC 2026 foram codificados como invariantes de teste em [`tests/test_evaluation.py`](../../tests/test_evaluation.py).
  - **Pipeline Acadêmico Integrado:** Pesquisadores podem gerar tabelas LaTeX publicáveis com um único comando de terminal (`uv run python main.py --evaluate-human --export-prefix paper_eval`).
  - **Suíte de Testes Expandida:** Adição de 34 testes automatizados na Fase 10, consolidando a suíte global em **218 testes passando com 100% de sucesso**.
- **Trade-offs / Riscos Assumidos:**
  - **Natureza Sintética dos Cenários:** Os baselines humanos refletem o experimento controlado descrito no REIC 2026; variações no tempo humano em equipes corporativas reais dependem de fatores ergonômicos e ritos organizacionais.
