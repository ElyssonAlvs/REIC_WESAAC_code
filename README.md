# Sprint Planning Multi-Agent System (LangGraph)

> **Implementação rigorosa, auditável e tipada de um Sistema Multiagente (SMA) para automação e otimização do planejamento de sprints no Scrum, utilizando a stack LangGraph + LangChain + LangSmith.**

Este repositório materializa a evolução prática e cientificamente auditável das propostas teóricas publicadas em:
1. **WESAAC 2025:** [*Agile Methodology and AI in Multi-Agent Systems: An agent for planning and executing sprints*](docs/papers/WESAAC_2025_Agile_MultiAgent.pdf) (19º Workshop-Escola de Sistemas de Agentes, seus Ambientes e Aplicações).
2. **REIC 2026:** [*Metodologia Ágil e IA em Sistemas Multiagentes: Avaliação Experimental de uma Arquitetura para Planejamento e Execução de Sprints*](docs/papers/REIC_2026_Metodologia_Agil_Multiagentes.pdf) (Revista Eletrônica de Iniciação Científica em Computação, SBC).

Consulte o [**Catálogo de Papers Científicos**](docs/papers/README.md) para resumos, autoria (UFC Quixadá) e transcrições completas.

---

## 🏛️ Arquitetura em 4 Camadas (Padrão LLMOps para Agentes)

Adotamos a organização de artefatos recomendada pelas melhores práticas de engenharia de IA e LLMOps, dividida em quatro camadas fundamentais:

```
REIC-WESAAC/
├── sprint_mas/             # 1. CÓDIGO: Lógica dos agentes, grafo LangGraph, estado, CLI e fábrica LLM
├── configs/                # 2. CONFIGURAÇÕES & PROMPTS: Prompts versionados como código (técnica BART)
│   ├── README.md
│   ├── models.yaml         # Hiperparâmetros, timeouts e seleção de modelos
│   └── prompts/            # System prompts isolados por especialista (YAML)
├── data/                   # 3. DADOS & CENÁRIOS: Procedência, dicionário e cenários A, B e C
│   ├── README.md           # Dicionário de dados das tarefas e perfis
│   ├── raw/                # Dados brutos originais do paper
│   └── processed/          # Cenários JSON validados via Pydantic
├── evals/                  # 4. AVALIAÇÃO & RUBRICAS: Golden dataset e critérios de dependência/FTE
│   ├── README.md           # Guia da camada de LLMOps e rubricas analíticas
│   ├── rubricas.md         # Métricas de sucesso, fórmulas e severidades
│   └── golden_dataset/     # Gabaritos de referência ótima dos cenários
├── reports/                # RELATÓRIOS & BENCHMARKS: Evidências científicas e comparativos
│   ├── README.md           # Guia de governança de relatórios e separação de artefatos
│   ├── published/          # Evidências oficiais congeladas para artigos (com manifest.json)
│   └── experiments/        # Pacotes canônicos leves de replicação experimental
├── artifacts/              # EXECUÇÕES LOCAIS: Espaço de trabalho ad-hoc (ignorado no Git)
│   ├── README.md           # Ciclo de vida de curadoria científica
│   └── runs/               # Execuções locais isoladas por <run_id>
├── tests/                  # QUALIDADE: Suíte de testes unitários e de integração (pytest)
├── docs/                   # CENTRAL DE DOCUMENTAÇÃO & GOVERNANÇA
│   ├── README.md           # Hub Central de Documentação do Projeto
│   ├── roadmap.md          # Histórico detalhado das Fases 1 a 14 de engenharia
│   ├── index.html          # Dashboard interativo com simulador de grafo e terminal
│   ├── system-card.md      # Ficha técnica do sistema (finalidade, limites e riscos)
│   ├── adr/                # Architecture Decision Records (ADRs 0001 a 0017)
│   │   └── README.md       # Catálogo unificado de decisões arquiteturais
│   ├── papers/             # Artigos científicos de referência (PDFs e transcrições)
│   │   └── README.md       # Resumos e mapeamento teórico (UFC Quixadá)
│   └── guides/             # Guias didáticos e pedagógicos
│       └── GUIA_APRENDIZADO.md # Manual completo: Teoria BDI, Blackboard e LangGraph
├── main.py                 # THIN ENTRYPOINT: Ponto de entrada enxuto (~45 linhas)
├── pyproject.toml          # GERENCIAMENTO: Manifesto do projeto gerido via uv
├── .env.example            # AMBIENTE: Template de configuração (Groq / Ollama / LangSmith)
└── .gitignore              # PROTEÇÃO: Bloqueio de secrets, logs pesados e artifacts/runs/*
```

---

## 🗺️ Roadmap de Implementação por Fases

O projeto foi executado sob a estratégia **"Dividir para Conquistar"**, estruturado em **14 fases incrementais** (100% homologadas), cobrindo desde a fundação inicial com Blackboard tipado e nós cognitivos híbridos até a separação física entre execuções locais e evidências publicadas:

- 📊 **Status Geral:** 14 de 14 Fases Concluídas (100% Homologado).
- 🧪 **Cobertura de Qualidade:** 340 testes automatizados cobrindo fluxos felizes, restrições e segurança estática.
- 🏛️ **Governança:** 17 Architecture Decision Records formalizadas no padrão Design System (ADRs 0001 a 0017).

> Para a linha do tempo completa, escopo detalhado de cada fase, datas de entrega e vínculos arquiteturais, consulte o [**Roadmap Detalhado de Engenharia (`docs/roadmap.md`)**](docs/roadmap.md).

---

## 🏛️ Decisões de Arquitetura (ADRs)

Todas as escolhas de design, garantias de integridade transacional, mitigação de riscos e substituições em relação ao fluxo legado no n8n estão formalizadas em documentos imutáveis no formato Design System / MADR em [`docs/adr/`](docs/adr/README.md):

| Grupo Temático | ADRs Cobertas | Foco e Impacto de Engenharia |
| :--- | :---: | :--- |
| **Fundação & Modelagem** | [0001](docs/adr/0001-migracao-n8n-para-langgraph.md), [0002](docs/adr/0002-padrao-blackboard-com-pydantic-e-sprintstate.md), [0003](docs/adr/0003-fabrica-hibrida-de-llms-groq-e-ollama.md), [0004](docs/adr/0004-padronizacao-de-cenarios-de-teste-e-data-loader.md), [0005](docs/adr/0005-prompts-como-codigo-e-ferramentas-deterministicas.md) | Migração do n8n para LangGraph, Blackboard em Pydantic v2 com redutor `add_messages`, fábrica híbrida (Groq/Ollama), Data Loader tipado e Prompts BART. |
| **Nós Especialistas & Grafo** | [0006](docs/adr/0006-agente-priorizacao-hibrido-bart-dag.md), [0007](docs/adr/0007-agente-alocacao-capacidade-skills.md), [0008](docs/adr/0008-agente-validador-deterministico-zero-llm.md), [0009](docs/adr/0009-orquestracao-ciclica-supervisor-langgraph-circuit-breaker.md) | Priorizador cognitivo-determinístico (0% de erro causal), Alocador com resolução de gargalo via `dev_C` e teto `dev_D`, Validador Zero LLM e Grafo Cíclico com Circuit Breaker. |
| **Observabilidade & Métricas** | [0010](docs/adr/0010-observabilidade-hibrida-langsmith-e-cli-executiva.md), [0011](docs/adr/0011-protocolo-benchmarking-automatizado-e-metricas-cientificas.md), [0012](docs/adr/0012-avaliacao-empirica-comparativo-humano-e-reic2026.md), [0015](docs/adr/0015-extracao-automatizada-metricas-langsmith-multi-modelo.md) | Telemetria BDI híbrida (Cloud/Local), motor de benchmarks multi-runs, confronto formal humano (speedup > 25.000x) e sincronização paginada LangSmith. |
| **Segurança & Reprodutibilidade** | [0013](docs/adr/0013-hardening-transversal-pentagono-defesa-e-verificacao-semantica.md), [0014](docs/adr/0014-pacote-reprodutibilidade-cientifica-e-consolidacao-documental.md), [0016](docs/adr/0016-recapitulacao-auditoria-homologacao-cientifica-1para1.md), [0017](docs/adr/0017-separacao-execucao-publicacao-manifesto-thin-cli.md) | Hardening do Pentágono (27 modelos `extra="forbid"`), replicação em 1 clique, DFS iterativo anti-DoS, isolamento offline no pytest, Thin CLI e manifesto criptográfico. |

Consulte o [**Catálogo Completo de ADRs (`docs/adr/README.md`)**](docs/adr/README.md) para matrizes de estado, diagramas de sequência e diretrizes de Do's & Don'ts.

---

## 📚 Trabalhos Científicos de Origem

O projeto baseia-se diretamente nas pesquisas pioneiras desenvolvidas na **Universidade Federal do Ceará (UFC — Campus Quixadá)**:

- 📕 **WESAAC 2025:** *Agile Methodology and AI in Multi-Agent Systems: An agent for planning and executing sprints*  
  [Visualizar PDF](docs/papers/WESAAC_2025_Agile_MultiAgent.pdf) &bull; [Transcrição Textual](docs/papers/wesaac_text.txt)
- 📕 **REIC 2026:** *Metodologia Ágil e IA em Sistemas Multiagentes: Avaliação Experimental de uma Arquitetura para Planejamento e Execução de Sprints*  
  [Visualizar PDF](docs/papers/REIC_2026_Metodologia_Agil_Multiagentes.pdf) &bull; [Transcrição Textual](docs/papers/reic_text.txt)

Para resumos analíticos, contexto histórico e links cruzados, visite o [**Hub de Papers Científicos**](docs/papers/README.md).

---

## 🗂️ Onde Encontrar Cada Artefato

| Tipo de Artefato | Localização | Está no Git? | Justificativa / Finalidade |
| :--- | :--- | :---: | :--- |
| **Código Fonte do SMA** | `sprint_mas/` e `main.py` | **Sim** | Nós cognitivos, grafos de estado, telemetria BDI, esquemas Pydantic, fábrica LLM e Thin CLI. |
| **Testes Automatizados** | `tests/` | **Sim** | Suíte pytest com 340 testes unitários e de integração (100% offline e sem mocks de rede). |
| **Prompts dos Agentes** | `configs/prompts/` | **Sim** | Prompts declarativos versionados em YAML com elicitação BART. |
| **Dicionário & Schemas** | `data/README.md` | **Sim** | Especificação formal dos dados de tarefas e perfis de desenvolvedores. |
| **Cenários de Teste (JSON)** | `data/processed/` | **Sim** | Datasets de teste dos Cenários A, B e C para replicação experimental. |
| **Rubricas de Avaliação** | `evals/rubricas.md` | **Sim** | Critérios analíticos e gabaritos ótimos de referência (*Ground Truth*). |
| **Coleção Postman/Insomnia** | `docs/collections/` | **Sim** | Request Specs v2.1.0 com asserções JS (`pm.test`) para validação de endpoints e replicação. |
| **Ficha Técnica (System Card)** | `docs/system-card.md` | **Sim** | Governança de riscos, limites operacionais e métricas de qualidade. |
| **Decisões de Arquitetura (ADRs)**| `docs/adr/` | **Sim** | Registro imutável de decisões de engenharia (ADRs 0001 a 0017). |
| **Artigos Científicos** | `docs/papers/` | **Sim** | PDFs originais e transcrições completas dos artigos WESAAC e REIC. |
| **Guia Didático de Aprendizado** | `docs/guides/GUIA_APRENDIZADO.md`| **Sim** | Referência pedagógica da transição teórica/prática (BDI e Blackboard). |
| **Dashboard Interativo** | `docs/index.html` | **Sim** | Interface web com simulador de grafo e terminal de testes interativo. |
| **Hub Central de Documentação** | `docs/README.md` | **Sim** | Ponto de entrada unificado para todos os manuais e relatórios técnicos. |
| **Evidências Oficiais Publicadas** | `reports/published/reic-2026/` | **Sim** | Tabelas (.csv, .md, .tex), `manifest.json` congelado e `metrics.json` do artigo. |
| **Relatórios Canônicos Leves** | `reports/experiments/` | **Sim** | Pacotes canônicos leves (`.json`, `.md`, `.csv`, `.tex`) versionados para reprodutibilidade científica. |
| **Execuções Locais de Trabalho** | `artifacts/runs/` | **Não** | Diretório ad-hoc ignorado pelo `.gitignore` para runs locais sem sujar o histórico. |
| **Logs Brutos Pesados** | `reports/experiments/` | **Não** | Ignorados pelo `.gitignore` (`*.jsonl`, `*.log`) para evitar inchaço do repositório. |
| **Chaves de API e Segredos** | `.env` | **Não** | Bloqueado pelo `.gitignore` (template de referência em `.env.example`). |

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- Python 3.12 instalado
- Gerenciador de pacotes [`uv`](https://docs.astral.sh/uv/)

### 2. Inicialização e Sincronização do Ambiente
```bash
git clone https://github.com/ElyssonAlvs/REIC_WESAAC_code.git REIC-WESAAC && cd REIC-WESAAC
uv venv --python 3.12
uv sync
```

### 3. Configuração do `.env`
Copie o modelo de ambiente:
```bash
cp .env.example .env
```
- Para utilizar **Groq Cloud:** configure `PROVIDER=groq` e adicione sua chave `GROQ_API_KEY=gsk_...`.
- Para utilizar **Ollama Local (Offline):** configure `PROVIDER=ollama` (com `llama3:latest` ativo no Ollama).

### 4. Modos de Execução da CLI e Observabilidade
O sistema suporta dois modos operacionais formalmente declarados no manifesto de procedência (`manifest.json`):
- **Modo Simulado / Fallback Determinístico (`--offline-mock`):** Executa o pipeline de agentes com nós analíticos gulosos de contingência que respeitam 100% das *Hard Constraints*, operando totalmente offline com zero chamadas externas e `provider=null` / `model=null`.
- **Modo Experimental com LLM:** Realiza deliberação cognitiva via modelos na nuvem (`--provider groq`) ou locais (`--provider ollama`), registrando os tokens e latências na plataforma LangSmith.

```bash
# Executar o Cenário B com trilha deliberativa BDI e diagrama Mermaid do grafo
uv run python main.py --scenario b --show-trace --show-graph

# Executar o Cenário A e exportar relatório estruturado em JSON
uv run python main.py --scenario a --json --output reports/experiments/scenario_a_run.json

# Executar benchmark automatizado dos Cenários A, B e C com 2 repetições e exportação tripla (.json, .md, .csv)
uv run python main.py --benchmark --scenarios a,b,c --runs 2 --export-prefix benchmark

# Executar avaliação empírica comparativa contra o benchmark humano com exportação quádrupla (.json, .md, .csv, .tex)
uv run python main.py --evaluate-human --scenarios a,b,c --runs 2 --export-prefix empirical_eval

# Executar auditoria de segurança contínua do Pentágono de Defesa (sub-segundo, zero LLM)
uv run python main.py --security-audit

# Executar a replicação científica completa em 1 clique (WESAAC 2025 & REIC 2026) com exportação quádrupla
uv run python main.py --reproduce-paper --offline-mock

# Sincronizar e agregar métricas empíricas multi-modelo via API do LangSmith com exportação quádrupla
uv run python main.py --sync-metrics --project REIC_WESAAC_code --export-prefix langsmith_metrics
```

#### 📊 Sincronização e Tabela de Métricas LangSmith Multi-Modelo
A flag `--sync-metrics` (ou o alias `--pull-langsmith`) conecta-se à API REST/SDK do LangSmith, extrai as execuções de telemetria das sessões BDI e gera agregações estatísticas por par `(model_name, scenario)`:

| Coluna | Descrição Técnica |
|---|---|
| `model_name` | Identificador do LLM avaliado (ex.: `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`). |
| `scenario` | Cenário experimental executado (`scenario_a`, `scenario_b`, `scenario_c`). |
| `runs_count` | Total de repetições empíricas analisadas para o modelo no cenário. |
| `mean_duration_ms` / `p95_duration_ms` | Média aritmética e Percentil 95 interpolado da latência de execução (ms). |
| `prompt` / `compl` / `total_tokens` | Médias por run de tokens de entrada, saída e total consumidos. |
| `total_cost_usd` | Custo financeiro acumulado em dólares (USD) reportado pela inferência. |
| `success_rate_pct` | Taxa de aprovação operacional percentual (0.0% a 100.0%). |

*Artefatos exportados atomicamente:* `.json` (canônico), `.md` (sumário executivo), `.csv` (com `\n` imune a CRCRLF) e `.tex` (tabela acadêmica em `booktabs` para WESAAC/REIC).

### 5. Execução da Suíte de Testes
```bash
uv run pytest tests/ -v
```
*Status esperado: 340 testes automatizados passando (100%).*

---

## 📖 Documentação Aprofundada
- 🎓 **Conceitos teóricos e aprendizado prático:** [`docs/guides/GUIA_APRENDIZADO.md`](docs/guides/GUIA_APRENDIZADO.md)
- 🏛️ **Decisões de Arquitetura (ADRs):** [`docs/adr/README.md`](docs/adr/README.md)
- 📚 **Artigos Científicos de Referência:** [`docs/papers/README.md`](docs/papers/README.md)
- 📋 **Ficha do Sistema (System Card):** [`docs/system-card.md`](docs/system-card.md)
- 🌐 **Dashboard Interativo:** [`docs/index.html`](docs/index.html)
- 📊 **Dicionário de Dados:** [`data/README.md`](data/README.md)
- 📖 **Hub Geral de Documentação:** [`docs/README.md`](docs/README.md)
