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
├── sprint_mas/             # 1. CÓDIGO: Lógica dos agentes, grafo LangGraph, estado e fábrica LLM
├── configs/                # 2. CONFIGURAÇÕES & PROMPTS: Prompts versionados como código (técnica BART)
│   ├── README.md
│   ├── models.yaml         # Hiperparâmetros, timeouts e seleção de modelos
│   └── prompts/            # System prompts isolados por especialista (YAML)
├── data/                   # 3. DADOS & CENÁRIOS: Procedência, dicionário e cenários A, B e C
│   ├── README.md           # Dicionário de dados das tarefas e perfis
│   ├── raw/                # Dados brutos originais do paper
│   └── processed/          # Cenários JSON validados via Pydantic
├── evals/                  # 4. AVALIAÇÃO & RUBRICAS: Golden dataset e critérios de dependência/FTE
│   ├── rubricas.md         # Métricas de sucesso, fórmulas e severidades
│   └── golden_dataset/     # Gabarito de referência dos cenários
├── reports/                # RELATÓRIOS & BENCHMARKS: Logs e comparativos M-Manual vs M-Agente
│   └── experiments/        # Saídas de benchmarks de tempo e resiliência
├── tests/                  # QUALIDADE: Suíte de testes unitários automatizados (pytest)
├── docs/                   # CENTRAL DE DOCUMENTAÇÃO & GOVERNANÇA
│   ├── README.md           # Hub Central de Documentação do Projeto
│   ├── index.html          # Dashboard interativo com simulador de grafo e terminal
│   ├── system-card.md      # Ficha técnica do sistema (finalidade, limites e riscos)
│   ├── adr/                # Architecture Decision Records (ADRs 0001 a 0011)
│   │   └── README.md       # Catálogo unificado de decisões arquiteturais
│   ├── papers/             # Artigos científicos de referência (PDFs e transcrições)
│   │   └── README.md       # Resumos e mapeamento teórico (UFC Quixadá)
│   └── guides/             # Guias didáticos e pedagógicos
│       └── GUIA_APRENDIZADO.md # Manual completo: Teoria BDI, Blackboard e LangGraph
├── main.py                 # CLI EXECUTIVA: Ponto de entrada com telemetria BDI e LangSmith
├── pyproject.toml          # GERENCIAMENTO: Manifesto do projeto gerido via uv
├── .env.example            # AMBIENTE: Template de configuração (Groq / Ollama / LangSmith)
└── .gitignore              # PROTEÇÃO: Bloqueio de secrets, logs pesados e caches
```

---

## 🗺️ Roadmap de Implementação por Fases

O projeto adota a estratégia **"Dividir para Conquistar"**, estruturado em 12 fases incrementais, auditáveis e testadas:

| Fase | Título | Foco Técnico / Escopo | Status |
| :---: | :--- | :--- | :---: |
| **1** | **Fundação & Contrato de Estado** | Configuração com `uv`, Pydantic v2 schemas, `SprintState` (Blackboard), fábrica híbrida de LLM (`ChatGroq` / `ChatOllama`) e testes unitários. | ✅ **Concluído** |
| **2** | **Dados & Cenários de Teste** | Estruturação reproduzível dos Cenários A, B e C do paper em `data/processed/scenario_*.json`, com parser tipado, validação de DAG e testes. | ✅ **Concluído** |
| **3** | **Ferramentas & Prompts (BART)** | Implementação de `@tool` determinísticas (cálculo de FTE, grafo de dependências) e system prompts em `configs/prompts/` baseados na técnica BART. | ✅ **Concluída (19/10/2026)** |
| **4** | **Agente de Priorização** | Nó cognitivo híbrido (Tool DAG + LLM BART + Kahn Min-Heap) assegurando matematicamente 0% de erro causal. | ✅ **Concluída (31/10/2026)** |
| **5** | **Agente de Alocação** | Nó cognitivo híbrido (BART + Tool Capacity + Match Skills) mitigando gargalos via dev_C e blindando dev_D (0.5 FTE). | ✅ **Concluída (31/10/2026)** |
| **6** | **Agente de Validação (Determinístico)** | Nó puro em Python que audita sem LLM se restrições de FTE e dependências foram violadas, forçando loops corretivos. | ✅ **Concluída (02/11/2026)** |
| **7** | **Supervisor & Montagem do Grafo** | Coordenação condicional, arestas cíclicas de feedback e compilação do grafo LangGraph com checkpointing (`MemorySaver`) e Circuit Breaker. | ✅ **Concluída (02/11/2026)** |
| **8** | **CLI & Observabilidade LangSmith** | Interface de linha de comando (`main.py`) e telemetria completa de traces de raciocínio BDI no LangSmith e local (`telemetry.py`). | ✅ **Concluída (03/11/2026)** |
| **9** | **Live Execution & Benchmarks (A, B, C)** | Bateria automatizada de benchmarks multi-cenário e multi-runs (`benchmarks.py` e `main.py --benchmark`), métricas estatísticas e exportação em `.json`, `.md` e `.csv`. | ✅ **Concluída (04/11/2026)** |
| **10** | **Avaliação Empírica & Comparativo Humano** | Confronto analítico direto das métricas do SMA contra o benchmark humano do artigo (765s vs SMA). | ⏳ *Próxima* |
| **11** | **Auditoria de Segurança & Verificação Semântica** | Auditoria formal do Pentágono de Defesa, diff audit estrito e checagem de semântica do implementado vs testado (Zero Scope Leak). | ⏳ *Pendente* |
| **12** | **Documentação Minimalista & Consolidação** | Síntese minimalista de markdowns de governança, empacotamento para replicação científica e atualização final do HTML interativo. | ⏳ *Pendente* |

---

## 🏛️ Decisões de Arquitetura (ADRs)

Todas as escolhas estruturais, mitigações de riscos e substituições em relação à abordagem original no n8n estão formalizadas no padrão Design System / MADR em [`docs/adr/`](docs/adr/README.md):

| ADR | Título | Data | Status | Decisão Técnica Resumida |
| :---: | :--- | :---: | :---: | :--- |
| **[0001](docs/adr/0001-migracao-n8n-para-langgraph.md)** | **Migração do n8n para a Stack LangGraph** | 2026-10-02 | `Aprovada` | Substituição da ferramenta low-code por grafos de estado tipados, cíclicos e testáveis, viabilizando observabilidade e loops corretivos. |
| **[0002](docs/adr/0002-padrao-blackboard-com-pydantic-e-sprintstate.md)** | **Padrão Blackboard com Pydantic v2 e TypedDict** | 2026-10-02 | `Aprovada` | Centralização da memória compartilhada em `SprintState` com redutor `add_messages` e validações de borda (`story_points > 0`, `0.0 <= fte <= 1.0`). |
| **[0003](docs/adr/0003-fabrica-hibrida-de-llms-groq-e-ollama.md)** | **Fábrica Híbrida de LLMs (Groq + Ollama)** | 2026-10-02 | `Aprovada` | Desacoplamento da infraestrutura de IA para alternar entre nuvem gratuita ultra-rápida (Groq) e execução local offline (Ollama). |
| **[0004](docs/adr/0004-padronizacao-de-cenarios-de-teste-e-data-loader.md)** | **Data Loader Tipado e Validação de DAG** | 2026-10-19 | `Aprovada` | Ingestão sintética reproduzível dos Cenários A, B e C com validação algorítmica de DAG ($O(V+E)$) contra dependências circulares. |
| **[0005](docs/adr/0005-prompts-como-codigo-e-ferramentas-deterministicas.md)** | **Prompts BART e Ferramentas Determinísticas** | 2026-10-19 | `Aprovada` | Prompts em YAML (`configs/prompts/*.yaml`), pureza analítica e ferramentas Python puras (`@tool`) com defesas anti-IDOR. |
| **[0006](docs/adr/0006-agente-priorizacao-hibrido-bart-dag.md)** | **Priorizador Híbrido Cognitivo-Determinístico** | 2026-10-20 | `Aprovada` | Arquitetura em 3 estágios (Tool DAG + LLM BART + Kahn Min-Heap) assegurando matematicamente 0% de erro causal e alinhamento estrito ao paper. |
| **[0007](docs/adr/0007-agente-alocacao-capacidade-skills.md)** | **Alocador de Recursos e Resolução de Gargalos via Perfil Fullstack** | 2026-10-31 | `Aprovada` | Alocação com mitigação de gargalo via dev_C (Fullstack) e blindagem de dev_D (0.5 FTE) com fallback determinístico. |
| **[0008](docs/adr/0008-agente-validador-deterministico-zero-llm.md)** | **Agente Validador Determinístico Multi-Dimensional com Zero LLM e Server Authority** | 2026-11-02 | `Aprovada` | Motor analítico em Python puro com 5 dimensões de auditoria, latência sub-milissegundo, Zero LLM e autoridade estrita em Story Points. |
| **[0009](docs/adr/0009-orquestracao-ciclica-supervisor-langgraph-circuit-breaker.md)** | **Orquestração Cíclica com Grafo LangGraph, Nó Corretivo de Escopo e Circuit Breaker Stateless** | 2026-11-02 | `Aprovada` | Topologia cíclica do StateGraph, poda analítica por capacidade (84 pts no Cenário B), Circuit Breaker stateless e Server Authority no supervisor. |
| **[0010](docs/adr/0010-observabilidade-hibrida-langsmith-e-cli-executiva.md)** | **Observabilidade Híbrida LangSmith da Deliberação BDI e CLI Executiva Segura** | 2026-11-03 | `Aprovada` | Telemetria dual (Cloud LangSmith + Local BDI Trace), sincronização `LANGSMITH_*`/`LANGCHAIN_*`, CLI `main.py` com códigos de saída padronizados e proteção anti-Path Traversal. |
| **[0011](docs/adr/0011-protocolo-benchmarking-automatizado-e-metricas-cientificas.md)** | **Protocolo de Benchmarking Automatizado e Coleta de Métricas Empíricas** | 2026-11-04 | `Aprovada` | Execução empírica automatizada dos Cenários A, B e C, isolamento estrito de `thread_id`, Server Authority em métricas de DAG/FTE/Skills, agregações estatísticas seguras e exportação tripla (.json, .md, .csv) com blindagem anti-Path Traversal. |

Acesse o [**Catálogo Completo de ADRs**](docs/adr/README.md) para consultar o histórico detalhado, matrizes de estado e diagramas.

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
| **Código Fonte do SMA** | `sprint_mas/` e `main.py` | **Sim** | Nós cognitivos, grafos de estado, telemetria BDI, esquemas Pydantic, fábrica LLM e CLI executiva. |
| **Testes Automatizados** | `tests/` | **Sim** | Suíte pytest com 184 testes unitários e de integração (100% offline e sem mocks de rede). |
| **Prompts dos Agentes** | `configs/prompts/` | **Sim** | Prompts declarativos versionados em YAML com elicitação BART. |
| **Dicionário & Schemas** | `data/README.md` | **Sim** | Especificação formal dos dados de tarefas e perfis de desenvolvedores. |
| **Cenários de Teste (JSON)** | `data/processed/` | **Sim** | Datasets de teste dos Cenários A, B e C para replicação experimental. |
| **Rubricas de Avaliação** | `evals/rubricas.md` | **Sim** | Critérios matemáticos de aceitação (dependência causal e sobrecarga FTE). |
| **Ficha Técnica (System Card)** | `docs/system-card.md` | **Sim** | Governança de riscos, limites operacionais e métricas de qualidade. |
| **Decisões de Arquitetura (ADRs)**| `docs/adr/` | **Sim** | Registro imutável de decisões de engenharia (ADRs 0001 a 0011). |
| **Artigos Científicos** | `docs/papers/` | **Sim** | PDFs originais e transcrições completas dos artigos WESAAC e REIC. |
| **Guia Didático de Aprendizado** | `docs/guides/GUIA_APRENDIZADO.md`| **Sim** | Referência pedagógica da transição teórica/prática (BDI e Blackboard). |
| **Dashboard Interativo** | `docs/index.html` | **Sim** | Interface web com simulador de grafo e terminal de testes interativo. |
| **Hub Central de Documentação** | `docs/README.md` | **Sim** | Ponto de entrada unificado para todos os manuais e relatórios técnicos. |
| **Logs de Experimentos Pesados** | `reports/experiments/` | **Não** | Ignorados pelo `.gitignore` (rastreados e versionados via LangSmith). |
| **Chaves de API e Segredos** | `.env` | **Não** | Bloqueado pelo `.gitignore` (template de referência em `.env.example`). |

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- Python 3.12 instalado
- Gerenciador de pacotes [`uv`](https://docs.astral.sh/uv/)

### 2. Inicialização e Sincronização do Ambiente
```bash
git clone https://github.com/SEU-USUARIO/REIC-WESAAC.git
cd REIC-WESAAC
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

### 4. Execução da CLI Executiva, Observabilidade BDI & Benchmarks
```bash
# Executar o Cenário B com trilha deliberativa BDI e diagrama Mermaid do grafo
uv run python main.py --scenario b --show-trace --show-graph

# Executar o Cenário A e exportar relatório estruturado em JSON
uv run python main.py --scenario a --json --output reports/experiments/scenario_a_run.json

# Executar benchmark automatizado dos Cenários A, B e C com 2 repetições e exportação tripla (.json, .md, .csv)
uv run python main.py --benchmark --scenarios a,b,c --runs 2 --export-prefix benchmark
```

### 5. Execução da Suíte de Testes
```bash
uv run pytest tests/ -v
```
*Status esperado: 184 testes automatizados passando (100%).*

---

## 📖 Documentação Aprofundada
- 🎓 **Conceitos teóricos e aprendizado prático:** [`docs/guides/GUIA_APRENDIZADO.md`](docs/guides/GUIA_APRENDIZADO.md)
- 🏛️ **Decisões de Arquitetura (ADRs):** [`docs/adr/README.md`](docs/adr/README.md)
- 📚 **Artigos Científicos de Referência:** [`docs/papers/README.md`](docs/papers/README.md)
- 📋 **Ficha do Sistema (System Card):** [`docs/system-card.md`](docs/system-card.md)
- 🌐 **Dashboard Interativo:** [`docs/index.html`](docs/index.html)
- 📊 **Dicionário de Dados:** [`data/README.md`](data/README.md)
- 📖 **Hub Geral de Documentação:** [`docs/README.md`](docs/README.md)
