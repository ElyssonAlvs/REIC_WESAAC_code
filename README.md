# Sprint Planning Multi-Agent System (LangGraph)

> **Implementação rigorosa, auditável e tipada de um Sistema Multiagente (SMA) para automação e otimização do planejamento de sprints no Scrum, utilizando a stack LangGraph + LangChain + LangSmith.**

Este repositório materializa a evolução prática e cientificamente auditável das propostas teóricas publicadas em:
1. **WESAAC 2025:** [*Agile Methodology and AI in Multi-Agent Systems: An agent for planning and executing sprints*](file:///c:/Users/elyss/Desktop/REIC-WESAAC/WESAAC_2025_Agile_MultiAgent.pdf) (19º Workshop-Escola de Sistemas de Agentes, seus Ambientes e Aplicações).
2. **REIC 2026:** [*Metodologia Ágil e IA em Sistemas Multiagentes: Avaliação Experimental de uma Arquitetura para Planejamento e Execução de Sprints*](file:///c:/Users/elyss/Desktop/REIC-WESAAC/REIC_2026_Metodologia_Agil_Multiagentes.pdf) (Revista Eletrônica de Iniciação Científica em Computação, SBC).

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
├── docs/                   # GOVERNANÇA & ARQUITETURA
│   ├── adr/                # Architecture Decision Records (ADRs) formais
│   └── system-card.md      # Ficha técnica do sistema (finalidade, limites e riscos)
├── DOCUMENTOS-TASK/        # PROCESSO: Planos, relatórios e handovers do Tech Manager Workflow
│   └── INDEX.md            # Catálogo cronológico de governança
├── GUIA_APRENDIZADO.md     # PEDAGOGIA: Livro-guia conceitual e prático da reimplementação
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
| **4** | **Agente de Priorização** | Nó cognitivo responsável por ordenar o backlog por valor de negócio e precedências lógicas. | ✅ **Concluída (31/10/2026)** |
| **5** | **Agente de Alocação** | Nó cognitivo responsável pelo casamento semântico entre competências dos desenvolvedores e carga de trabalho. | ⏳ *Próxima* |
| **6** | **Agente de Validação (Determinístico)** | Nó puro em Python que audita sem LLM se restrições de FTE e dependências foram violadas, forçando loops corretivos. | ⏳ *Pendente* |
| **7** | **Supervisor & Montagem do Grafo** | Coordenação condicional, arestas cíclicas de feedback e compilação do grafo LangGraph com checkpointing. | ⏳ *Pendente* |
| **8** | **CLI & Observabilidade LangSmith** | Interface de linha de comando (`main.py`) e telemetria completa de traces de raciocínio no LangSmith. | ⏳ *Pendente* |
| **9** | **Live Execution & Benchmarks (A, B, C)** | Execução ao vivo com o servidor/grafo dos 3 cenários e captura empírica dos tempos de inferência e tokens. | ⏳ *Pendente* |
| **10** | **Avaliação Empírica & Comparativo Humano** | Confronto analítico direto das métricas do SMA contra o benchmark humano do artigo (765s vs SMA). | ⏳ *Pendente* |
| **11** | **Auditoria de Segurança & Verificação Semântica** | Auditoria formal do Pentágono de Defesa, diff audit estrito e checagem de semântica do implementado vs testado (Zero Scope Leak). | ⏳ *Pendente* |
| **12** | **Documentação Minimalista & Consolidação** | Síntese minimalista de markdowns de governança, empacotamento para replicação científica e atualização final do HTML interativo. | ⏳ *Pendente* |

---

## 📅 Histórico de Entregas e Decisões Técnicas

### 🗓️ 2026-10-02 — Entrega da Fase 1: Fundação & Contrato de Estado
- **Status:** ✅ Aprovado com 100% dos testes unitários passando (25/25 em 0.74s).
- **Documentos de Governança Emitidos:**
  - 📋 [Plano de Implementação da Fase 1](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-02_plano-fase1-fundacao.md)
  - 📊 [Relatório Final da Fase 1](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-02_relatorio-fase1-fundacao.md)
  - 🔌 [Pacote de Contexto da Fase 1](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-02_contexto-fase1-fundacao.md)

#### Architecture Decision Records (ADRs) Registrados:
1. **[ADR 0001: Migração do n8n para LangGraph](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/0001-migracao-n8n-para-langgraph.md)** — Substituição da ferramenta low-code por grafos de estado tipados, cíclicos e testáveis.
2. **[ADR 0002: Padrão Blackboard com Pydantic v2 e TypedDict](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/0002-padrao-blackboard-com-pydantic-e-sprintstate.md)** — Centralização da memória compartilhada em `SprintState` com redutor `add_messages` e validações de borda (`story_points > 0`, `0.0 <= fte <= 1.0`).
3. **[ADR 0003: Fábrica Híbrida de LLMs (Groq + Ollama)](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/0003-fabrica-hibrida-de-llms-groq-e-ollama.md)** — Desacoplamento da infraestrutura de IA com Groq na nuvem (grátis/rápido) e Ollama local offline.

### 🗓️ 2026-10-19 — Entrega da Fase 2: Dados & Cenários de Teste Reproduzíveis
- **Status:** ✅ Aprovado com 100% dos testes unitários passando (37/37 em 1.21s).
- **Documentos de Governança Emitidos:**
  - 📋 [Plano de Implementação da Fase 2](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-19_plano-fase2-dados-cenarios.md)
  - 📊 [Relatório Final da Fase 2](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-19_relatorio-fase2-dados-cenarios.md)
  - 🔌 [Pacote de Contexto da Fase 2](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-19_contexto-fase2-dados-cenarios.md)

#### Architecture Decision Records (ADRs) Registrados:
4. **[ADR 0004: Padronização de Cenários de Teste, Data Loader e Validação de DAG](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/0004-padronizacao-de-cenarios-de-teste-e-data-loader.md)** — Ingestão estruturada de tarefas e desenvolvedores com validação algorítmica de DAG ($O(V + E)$) contra dependências circulares e órfãs.

### 🗓️ 2026-10-19 — Entrega da Fase 3: Ferramentas Determinísticas (`@tool`) e Prompts Versionados (Técnica BART)
- **Status:** ✅ Aprovado com 100% dos testes unitários passando (66/66 em 0.61s).
- **Documentos de Governança Emitidos:**
  - 📋 [Plano de Implementação da Fase 3](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-19_plano-fase3-ferramentas-prompts.md)
  - 🛡️ [Parecer Técnico de QA da Fase 3](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-19_parecer-qa-fase3-ferramentas-prompts.md)

#### Architecture Decision Records (ADRs) Registrados:
5. **[ADR 0005: Prompts como Código (YAML) e Ferramentas Determinísticas (@tool)](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/0005-prompts-como-codigo-e-ferramentas-deterministicas.md)** — Desacoplamento estrito entre instruções linguísticas (BART) e cálculos determinísticos em Python com proteção anti-IDOR e limites numéricos defensivos.

### 🗓️ 2026-10-31 — Entrega da Fase 4: Agente de Priorização (Product Owner Node)
- **Status:** ✅ Aprovado com 100% dos testes unitários passando (77/77 em 1.01s).
- **Documentos de Governança Emitidos:**
  - 📋 [Plano de Implementação da Fase 4](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-20_plano-fase4-agente-priorizacao.md)
  - 🛡️ [Parecer Técnico de QA da Fase 4](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/2026-10-31_parecer-qa-fase4-agente-priorizacao.md)

#### Architecture Decision Records (ADRs) Registrados:
6. **[ADR 0006: Arquitetura Híbrida Cognitivo-Determinística do Agente de Priorização](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/0006-agente-priorizacao-hibrido-bart-dag.md)** — Orquestração em 3 estágios (Tool-Augmented Context, deliberação semântica BART e guardião pós-LLM com fallback de Kahn ponderado por min-heap) assegurando matematicamente 0% de erro causal no DAG de dependências.

---

## 🗂️ Onde Encontrar Cada Artefato

| Tipo de Artefato | Localização | Está no Git? | Justificativa / Ferramenta |
| :--- | :--- | :---: | :--- |
| **Código Fonte do SMA** | `sprint_mas/` | **Sim** | Lógica de nós, agentes, estado e fábrica. |
| **Testes Unitários** | `tests/` | **Sim** | Suíte pytest com mocks (garantia de regressão zero). |
| **Prompts dos Agentes** | `configs/prompts/` | **Sim** | Prompts são tratados como código de produção (YAML). |
| **Dicionário & Schemas** | `data/README.md` | **Sim** | Especificação formal dos dados de tarefas e devs. |
| **Cenários de Teste (JSON)** | `data/processed/` | **Sim** | Datasets de teste sintéticos (pequenos e determinísticos). |
| **Rubricas de Avaliação** | `evals/rubricas.md` | **Sim** | Critérios formais de aceitação do plano gerado. |
| **Ficha Técnica (System Card)** | `docs/system-card.md` | **Sim** | Governança de riscos, limitações e escopo. |
| **Decisões Arquiteturais (ADRs)**| `docs/adr/` | **Sim** | Histórico imutável de decisões de engenharia. |
| **Processo e Tarefas** | `DOCUMENTOS-TASK/` | Local / Git | Governança ágil de planos e relatórios por entrega. |
| **Guia Didático de Estudo** | `GUIA_APRENDIZADO.md`| **Sim** | Referência pedagógica da transição teórica/prática. |
| **Logs de Experimentos Pesados** | `reports/experiments/` | **Não** | Ignorados pelo `.gitignore` (rastreados via LangSmith). |
| **Chaves de API e Secrets** | `.env` | **Não** | Bloqueado pelo `.gitignore` (template em `.env.example`). |

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- Python 3.12 instalado
- Gerenciador de pacotes [`uv`](https://docs.astral.sh/uv/)

### 2. Inicialização e Sincronização do Ambiente
```powershell
cd c:\Users\elyss\Desktop\REIC-WESAAC
uv venv --python 3.12
uv sync
```

### 3. Configuração do `.env`
Copie o modelo de ambiente:
```powershell
copy .env.example .env
```
- Para utilizar **Groq Cloud:** configure `PROVIDER=groq` e adicione sua chave `GROQ_API_KEY=gsk_...`.
- Para utilizar **Ollama Local (Offline):** configure `PROVIDER=ollama` (com `llama3:latest` ativo no Ollama).

### 4. Execução da Suíte de Testes
```powershell
uv run pytest tests/ -v
```
*Status esperado: 77 testes automatizados passando (100% em ~1.01s).*

---

## 📖 Documentação Aprofundada
- 🎓 **Conceitos teóricos e aprendizado prático:** [`GUIA_APRENDIZADO.md`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/GUIA_APRENDIZADO.md).
- 🏛️ **Decisões de Arquitetura (ADRs):** [`docs/adr/`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/adr/).
- 📋 **Ficha do Sistema:** [`docs/system-card.md`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/docs/system-card.md).
- 📊 **Dicionário de Dados:** [`data/README.md`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/data/README.md).
- 📜 **Histórico de Governança:** [`DOCUMENTOS-TASK/INDEX.md`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/DOCUMENTOS-TASK/INDEX.md).
