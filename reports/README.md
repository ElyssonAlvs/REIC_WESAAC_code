# Relatórios de Experimentos e Métricas — `reports/`

> **Diretório destinado a armazenar os resultados de experimentos, relatórios de benchmark e comparativos quantitativos entre humanos e o SMA.**

---

## 📁 Estrutura

- `reports/README.md`: Este guia de padrões de experimentação.
- `reports/experiments/`: Logs e saídas estruturadas de testes de estresse (Cenário C), tempos de inferência e comparação direta com o benchmark humano (M-Manual vs. M-Agente).
- Arquivos de logs volumosos (`*.log`, `*.jsonl`) são automaticamente ignorados pelo `.gitignore`.

---

## 📊 Template de Registro de Experimento

Ao rodar um experimento de benchmark, gere um registro no formato:

```markdown
# Experimento: Benchmark Cenário B (30 Tarefas)
- **Data/Hora:** 2026-10-02T...
- **Provedor:** Groq (llama-3.1-8b-instant)
- **Temperatura:** 0.0
- **Tempo de Execução:** 4.12s
- **Taxa de Sucesso de Validação:** 100%
- **Violações de FTE:** 0
- **Violações de Dependência:** 0
- **Trace LangSmith:** https://smith.langchain.com/...
```
