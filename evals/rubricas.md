# Rubricas e Critérios de Avaliação — `evals/`

> **Especificação das regras formais e rubricas de avaliação quantitativa e qualitativa das entregas do Sistema Multiagente (SMA).**

---

## 🎯 1. Critérios de Avaliação Lógica (Fidelidade do Plano)

| Critério | Peso | Fórmula / Verificação | Meta | Severidade da Falha |
| :--- | :---: | :--- | :---: | :---: |
| **Integridade de Dependências** | Crítico | Para toda tarefa $T_i$ dependente de $T_j$, $T_j$ deve estar agendada na mesma sprint ou concluída previamente. | 100% | **Crítica** (invalida o plano) |
| **Respeito ao Limite de FTE** | Crítico | $\sum \text{Points}(dev_k) \le \text{Capacidade}(dev_k \cdot \text{FTE})$. Ex: $dev\_D$ (0.5 FTE) não pode receber mais de 50% dos pontos médios. | 100% | **Crítica** (sobrecarga de desenvolvedor) |
| **Afinidade de Competências** | Alto | O desenvolvedor alocado deve possuir a habilidade requerida pela tarefa (`skill_required` $\in$ `dev.skills`). | $\ge 95\%$ | Alta (risco de impedimento técnico) |
| **Mitigação de Gargalo** | Médio | Tarefas de backend em excesso devem ser absorvidas preferencialmente por desenvolvedores fullstack (`dev_C`). | Observado | Média |

---

## ⏱️ 2. Critérios de Desempenho Operacional

| Métrica | Benchmark Humano (Scrum Master) | Alvo do SMA (LangGraph) |
| :--- | :--- | :--- |
| **Tempo de Execução (Cenário B - 30 tasks)** | 765 segundos (12 min 45s) | $\le 10$ segundos |
| **Taxa de Erro Lógico** | 0% | 0% |
| **Fadiga Cognitiva** | Alta fadiga relatada | Zero esforço humano manual |
| **Resiliência (Cenário C - Estresse)** | Inviável humanamente | $\ge 99\%$ de taxa de sucesso |

---

## 📋 3. Estrutura do `golden_dataset/`
O subdiretório `evals/golden_dataset/` armazena o "gabarito" (ground truth):
- Arquivos `.json` com o planejamento ótimo de referência para cada cenário.
- Utilizado por testes automatizados de avaliação de regressão de qualidade da IA.
