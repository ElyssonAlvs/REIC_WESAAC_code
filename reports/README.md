# Relatórios de Experimentos e Métricas — `reports/`

> **Diretório destinado a armazenar os resultados de experimentos, relatórios de benchmark, comparativos quantitativos entre humanos e o SMA e telemetria científica reproduzível.**

Seguindo as melhores práticas de Engenharia de Software e MLOps/LLMOps:
- **Relatórios Canônicos Leves (`.json`, `.md`, `.csv`, `.tex`):** São mantidos e versionados no Git para garantir **reprodutibilidade científica auditável e imediata** sem necessidade de refazer todas as inferências de rede.
- **Logs Brutos Pesados (`*.log`, `*.jsonl`):** São ignorados automaticamente pelo `.gitignore` para prevenir sobrecarga de versionamento do repositório.

---

## 📁 Pacotes Canônicos Oficiais (`reports/experiments/`)

O diretório `reports/experiments/` hospeda 5 suítes canônicas padronizadas geradas via CLI executiva (`main.py`):

| Prefixo do Pacote | Formatos Emitidos | Comando de Geração | Finalidade Científica e Escopo |
|---|:---:|---|---|
| **`benchmark.*`** | `.json`, `.md`, `.csv` | `uv run python main.py -b --offline-mock --export-prefix benchmark` | Métricas estatísticas de tempo (média, desvio padrão, mediana, P95), taxa de aprovação operacional (100%) e contagem de violações causais de DAG e capacidade FTE nos Cenários A, B e C. |
| **`empirical_eval.*`** | `.json`, `.md`, `.csv`, `.tex` | `uv run python main.py -e --offline-mock --export-prefix empirical_eval` | Confronto formal entre os três paradigmas: Planejamento Manual humano (765s), n8n (4.2s) e SMA LangGraph. Calcula speedup ($\approx 182\times$), redução de tempo (99.45%) e validação da mitigação do gargalo qualitativo da Seção 6.3 do REIC 2026. |
| **`replication_bundle.*`** | `.json`, `.md`, `.csv`, `.tex` | `uv run python main.py --reproduce-paper --offline-mock --export-prefix replication_bundle` | Orquestração experimental de 1 clique que executa em sequência: benchmarks A/B/C, avaliação empírica e auditoria do Pentágono de Defesa, atestando conformidade com WESAAC 2025 e REIC 2026. |
| **`security_semantic_audit.*`** | `.json`, `.md` | `uv run python main.py --security-audit --export-prefix security_semantic_audit` | Auditoria estática e dinâmica de sub-segundo cobrindo os 5 pilares do Pentágono de Defesa Expandido, reflexão dinâmica de 26/26 modelos Pydantic v2 com `extra="forbid"`, teste de DFS tricromático iterativo anti-DoS e verificação científica 1:1. |
| **`langsmith_metrics.*`** | `.json`, `.md`, `.csv`, `.tex` | `uv run python main.py --sync-metrics --export-prefix langsmith_metrics` | Extração programática de telemetria empírica via SDK do LangSmith (`Client.list_runs`), filtragem resiliente, agregações P95 interpoladas multi-modelo, custos em USD e tabela em LaTeX booktabs. |

---

## 📄 Especificação dos Formatos Canônicos

Cada pacote experimental é exportado de forma atômica e segura, validado por `validate_safe_benchmark_path` contra vulnerabilidades de *Path Traversal*:

1. **JSON Canônico (`.json`):**
   - Serialização tipada estrita a partir de modelos Pydantic v2 com `extra="forbid"`.
   - Utilizado para consumo programático por dashboards, pipelines CI/CD ou coleções Postman/Newman.
2. **Markdown Executivo (`.md`):**
   - Tabelas resumidas com formatação legível para humanos, destacando métricas-chave, taxas de sucesso e avisos operacionais.
3. **CSV Tabular (`.csv`):**
   - Gerado com `csv.writer`, `lineterminator="\n"` e gravação com `newline=""`.
   - Imune a retornos de carro duplos (`\r\r\n` ou CRCRLF) gerados pelo ecossistema Windows, assegurando conformidade estrita em pipelines Linux/macOS.
4. **LaTeX Compilável (`.tex`):**
   - Tabelas acadêmicas completas formatadas com o pacote `booktabs` (`\toprule`, `\midrule`, `\bottomrule`).
   - Caracteres reservados (`_`, `&`, `%`) sanitizados automaticamente para inclusão direta em artigos científicos submetidos à SBC, IEEE ou ACM.

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

## 📊 Template de Registro de Experimento Manual

Ao rodar um experimento pontual exploratório, registre no formato padronizado:

```markdown
# Experimento: Benchmark Cenário B (30 Tarefas)
- **Data/Hora:** 2026-11-06T20:00:00Z
- **Provedor:** Groq (openai/gpt-oss-20b)
- **Temperatura:** 0.0
- **Tempo de Execução:** 4.12s
- **Taxa de Sucesso de Validação:** 100%
- **Violações de FTE:** 0
- **Violações de Dependência:** 0
- **Trace LangSmith:** https://smith.langchain.com/...
```
