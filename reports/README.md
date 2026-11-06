# Relatórios de Experimentos e Métricas — `reports/`

> **Diretório destinado a armazenar os resultados de experimentos, relatórios de benchmark e comparativos quantitativos entre humanos e o SMA.**

---

## 📁 Estrutura

- `reports/README.md`: Este guia de padrões de experimentação.
- `reports/experiments/`: Logs e saídas estruturadas de testes de estresse (Cenário C), tempos de inferência e comparação direta com o benchmark humano (M-Manual vs. M-Agente).
- Arquivos de logs volumosos (`*.log`, `*.jsonl`) são automaticamente ignorados pelo `.gitignore`.

---

## 🤖 Catálogo de Modelos Ativos Suportados

Para garantir reprodutibilidade experimental fidedigna, as planilhas e relatórios discriminam explicitamente o provedor e modelo utilizados:

| Provedor | Identificador do Modelo (`model_name`) | Contexto de Uso Recomendado |
|---|---|---|
| **Groq** | `openai/gpt-oss-120b` | Modelo primário de alta capacidade para deliberação complexa |
| **Groq** | `qwen/qwen3.8-27b` | Modelo secundário balanceado para testes comparativos |
| **Groq** | `openai/gpt-oss-20b` | Modelo padrão de referência atual no `.env` |
| **Ollama** | `llama3:latest` | Inferência local on-premises sem dependência de internet |
| **Offline** | `deterministic-fallback` | Mock offline determinístico (0ms latência de API) para CI/CD |

---

## 📊 Template de Registro de Experimento

Ao rodar um experimento de benchmark ou reprodução científica, gere um registro no formato:

```markdown
# Experimento: Benchmark Cenário B (30 Tarefas)
- **Data/Hora:** 2026-11-06T...
- **Provedor:** Groq (openai/gpt-oss-20b)
- **Temperatura:** 0.0
- **Tempo de Execução:** 4.12s
- **Taxa de Sucesso de Validação:** 100%
- **Violações de FTE:** 0
- **Violações de Dependência:** 0
- **Trace LangSmith:** https://smith.langchain.com/...
```
