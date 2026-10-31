# 📚 Central de Documentação e Governança Técnica

> **Hub unificado de documentação do projeto Sprint Planning Multi-Agent System (LangGraph).**

Bem-vindo ao repositório central de documentação e engenharia. Aqui você encontra todos os artefatos teóricos, decisões arquiteturais, manuais pedagógicos e a ficha técnica completa do sistema.

---

## 🧭 Mapa de Navegação da Documentação

```
docs/
├── README.md                 # Este Hub Central de Documentação
├── index.html                # 🌐 Dashboard Interativo com Simulador do Grafo e Terminal de Testes
├── system-card.md            # 🛡️ Ficha Técnica: Finalidade, Limitações, Riscos e Métricas
├── adr/                      # 🏛️ Catálogo de Decisões de Arquitetura (ADRs 0001 a 0006)
│   ├── README.md             # Índice Completo e Sumário Executivo das ADRs
│   ├── 0001-migracao-n8n-para-langgraph.md
│   ├── 0002-padrao-blackboard-com-pydantic-e-sprintstate.md
│   ├── 0003-fabrica-hibrida-de-llms-groq-e-ollama.md
│   ├── 0004-padronizacao-de-cenarios-de-teste-e-data-loader.md
│   ├── 0005-prompts-como-codigo-e-ferramentas-deterministicas.md
│   └── 0006-agente-priorizacao-hibrido-bart-dag.md
├── papers/                   # 📚 Trabalhos Científicos de Referência (UFC Quixadá)
│   ├── README.md             # Resumos, Autoria e Mapeamento Científico
│   ├── WESAAC_2025_Agile_MultiAgent.pdf
│   ├── REIC_2026_Metodologia_Agil_Multiagentes.pdf
│   ├── wesaac_text.txt       # Transcrição Textual Completa
│   └── reic_text.txt         # Transcrição Textual Completa
└── guides/                   # 🎓 Guias Didáticos e Referência Prática
    └── GUIA_APRENDIZADO.md   # Guia Completo: Teoria BDI, Blackboard e Passo a Passo
```

---

## 🏛️ 1. Decisões Arquiteturais (ADRs)
Todas as decisões de design, migração e conformidade lógica estão registradas em documentos imutáveis no formato Design System / MADR:
- 📖 [**Catálogo de ADRs (`docs/adr/README.md`)**](./adr/README.md)
  - [ADR 0001: Migração do n8n para a Stack LangGraph](./adr/0001-migracao-n8n-para-langgraph.md)
  - [ADR 0002: Padrão Blackboard com Pydantic v2 e TypedDict](./adr/0002-padrao-blackboard-com-pydantic-e-sprintstate.md)
  - [ADR 0003: Fábrica Híbrida de LLMs (Groq + Ollama)](./adr/0003-fabrica-hibrida-de-llms-groq-e-ollama.md)
  - [ADR 0004: Data Loader Tipado e Validação de DAG](./adr/0004-padronizacao-de-cenarios-de-teste-e-data-loader.md)
  - [ADR 0005: Prompts como Código (BART) e Ferramentas Determinísticas](./adr/0005-prompts-como-codigo-e-ferramentas-deterministicas.md)
  - [ADR 0006: Priorizador Híbrido Cognitivo-Determinístico (0% Erro Causal)](./adr/0006-agente-priorizacao-hibrido-bart-dag.md)

---

## 📚 2. Trabalhos Científicos de Origem (Papers)
O projeto reimplementa e expande duas publicações dos pesquisadores da **Universidade Federal do Ceará (UFC — Campus Quixadá)**:
- 📖 [**Catálogo de Papers (`docs/papers/README.md`)**](./papers/README.md)
  - **WESAAC 2025:** *Agile Methodology and AI in Multi-Agent Systems: An agent for planning and executing sprints* ([PDF](./papers/WESAAC_2025_Agile_MultiAgent.pdf) | [Texto](./papers/wesaac_text.txt))
  - **REIC 2026:** *Metodologia Ágil e IA em Sistemas Multiagentes: Avaliação Experimental de uma Arquitetura para Planejamento e Execução de Sprints* ([PDF](./papers/REIC_2026_Metodologia_Agil_Multiagentes.pdf) | [Texto](./papers/reic_text.txt))

---

## 🎓 3. Guias de Aprendizado & Teoria
Para desenvolvedores, estudantes e pesquisadores que desejam entender em detalhes a transição do modelo *low-code* visual para arquiteturas de agentes com grafos de estado tipados:
- 📖 [**Guia de Aprendizado (`docs/guides/GUIA_APRENDIZADO.md`)**](./guides/GUIA_APRENDIZADO.md)
  - Fundamentos do Modelo BDI (Belief–Desire–Intention) no LangGraph
  - O Padrão Blackboard para comunicação entre agentes heterogêneos
  - O redutor `add_messages` e prevenção de sobrescrita de memória
  - Laboratório prático de execução e validação de restrições

---

## 🛡️ 4. Ficha Técnica do Sistema (System Card)
Documento oficial de governança que detalha o escopo de uso, limitações, matriz de riscos e estratégias de segurança implementadas:
- 📖 [**System Card (`docs/system-card.md`)**](./system-card.md)
  - Finalidade pretendida e público-alvo
  - Papéis dos agentes cognitivos e nós determinísticos
  - Tabela de riscos críticos e mitigações (anti-IDOR, teto de FTE, prevenção de ciclos)
  - Métricas de sucesso empírico

---

## 🌐 5. Dashboard Interativo
Uma interface visual rica em HTML5 e TailwindCSS para exploração interativa do sistema:
- 🖥️ [**Dashboard Interativo (`docs/index.html`)**](./index.html)
  - Visualizador e simulador de fluxo do Grafo LangGraph
  - Linha do tempo e progresso do Roadmap em 12 fases
  - Visualizador de código com comparativos estruturais
  - Terminal interativo com filtragem por módulo dos 77 testes automatizados

---

## 🏠 Navegação Externa
- 🚀 [README Principal do Projeto](../README.md)
- 🧪 [Diretório de Testes Automatizados](../tests/)
- ⚙️ [Configurações e Prompts YAML](../configs/prompts/)
- 📊 [Datasets e Dicionário de Dados](../data/)
