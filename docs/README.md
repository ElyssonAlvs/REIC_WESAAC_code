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
├── collections/              # 📬 Coleção Executiva Postman/Insomnia (Request Specs v2.1.0)
│   └── sprint_mas_postman_collection.json
├── adr/                      # 🏛️ Catálogo de Decisões de Arquitetura (ADRs 0001 a 0016)
│   ├── README.md             # Índice Completo e Sumário Executivo das ADRs
│   ├── 0001-migracao-n8n-para-langgraph.md
│   ├── 0002-padrao-blackboard-com-pydantic-e-sprintstate.md
│   ├── 0003-fabrica-hibrida-de-llms-groq-e-ollama.md
│   ├── 0004-padronizacao-de-cenarios-de-teste-e-data-loader.md
│   ├── 0005-prompts-como-codigo-e-ferramentas-deterministicas.md
│   ├── 0006-agente-priorizacao-hibrido-bart-dag.md
│   ├── 0007-agente-alocacao-capacidade-skills.md
│   ├── 0008-agente-validador-deterministico-zero-llm.md
│   ├── 0009-orquestracao-ciclica-supervisor-langgraph-circuit-breaker.md
│   ├── 0010-observabilidade-hibrida-langsmith-e-cli-executiva.md
│   ├── 0011-protocolo-benchmarking-automatizado-e-metricas-cientificas.md
│   ├── 0012-avaliacao-empirica-comparativo-humano-e-reic2026.md
│   ├── 0013-hardening-transversal-pentagono-defesa-e-verificacao-semantica.md
│   ├── 0014-pacote-reprodutibilidade-cientifica-e-consolidacao-documental.md
│   ├── 0015-extracao-automatizada-metricas-langsmith-multi-modelo.md
│   └── 0016-recapitulacao-auditoria-homologacao-cientifica-1para1.md
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
  - [ADR 0007: Alocador de Recursos e Resolução de Gargalos via Perfil Fullstack](./adr/0007-agente-alocacao-capacidade-skills.md)
  - [ADR 0008: Agente Validador Determinístico Multi-Dimensional com Zero LLM e Server Authority](./adr/0008-agente-validador-deterministico-zero-llm.md)
  - [ADR 0009: Orquestração Cíclica com Grafo LangGraph, Nó Corretivo de Escopo e Circuit Breaker Stateless](./adr/0009-orquestracao-ciclica-supervisor-langgraph-circuit-breaker.md)
  - [ADR 0010: Observabilidade Híbrida LangSmith da Deliberação BDI e CLI Executiva Segura](./adr/0010-observabilidade-hibrida-langsmith-e-cli-executiva.md)
  - [ADR 0011: Protocolo de Benchmarking Automatizado e Coleta de Métricas Empíricas](./adr/0011-protocolo-benchmarking-automatizado-e-metricas-cientificas.md)
  - [ADR 0012: Avaliação Empírica, Comparativo Humano (M-Manual vs n8n) e Rastreabilidade Científica REIC 2026](./adr/0012-avaliacao-empirica-comparativo-humano-e-reic2026.md)
  - [ADR 0013: Hardening Transversal do Pentágono de Defesa, Verificação Semântica Contínua e Imunidade a DoS de Grafos](./adr/0013-hardening-transversal-pentagono-defesa-e-verificacao-semantica.md)
  - [ADR 0014: Pacote de Reprodutibilidade Científica, Execução em 1 Clique e Consolidação Documental](./adr/0014-pacote-reprodutibilidade-cientifica-e-consolidacao-documental.md)
  - [ADR 0015: Extração Automatizada de Métricas Empíricas via API do LangSmith e Agregação Multi-Modelo](./adr/0015-extracao-automatizada-metricas-langsmith-multi-modelo.md)
  - [ADR 0016: Recapitulação Integral, Hardening do Grafo e Homologação Científica 1:1 com WESAAC 2025 e REIC 2026](./adr/0016-recapitulacao-auditoria-homologacao-cientifica-1para1.md)

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
  - Pacote de Reprodutibilidade Científica & Execução em 1 Clique com Coleção Postman (Capítulo 9)

---

## 🛡️ 4. Ficha Técnica do Sistema (System Card)
Documento oficial de governança que detalha o escopo de uso, limitações, matriz de riscos e estratégias de segurança implementadas:
- 📖 [**System Card (`docs/system-card.md`)**](./system-card.md)
  - Finalidade pretendida e público-alvo
  - Papéis dos agentes cognitivos e nós determinísticos
  - Tabela de riscos críticos e mitigações (anti-IDOR, teto de FTE, prevenção de ciclos)
  - Métricas de sucesso empírico e conformidade científica

---

## 📬 5. Coleção Executiva de Request Specs (Postman/Insomnia)
Suíte formal de requisições padronizadas no formato Postman Collection v2.1.0 para validação de contratos e testes automatizados:
- 📬 [**Coleção Postman (`docs/collections/sprint_mas_postman_collection.json`)**](./collections/sprint_mas_postman_collection.json)
  - 5 pastas modulares cobrindo Cenários A/B/C, Benchmarks, Avaliação Empírica, Pentágono e Reprodução Científica
  - Testes automatizados embutidos em JavaScript (`pm.test`) com asserções estritas de governança e validação de tetos de FTE
  - Execução contínua em CI/CD via Newman

---

## 🌐 6. Dashboard Interativo
Uma interface visual rica em HTML5 e TailwindCSS para exploração interativa do sistema:
- 🖥️ [**Dashboard Interativo (`docs/index.html`)**](./index.html)
  - Visualizador e simulador de fluxo do Grafo LangGraph
  - Linha do tempo e progresso do Roadmap em 13 fases (100% concluído)
  - Visualizador de código com comparativos estruturais
  - Terminal interativo com filtragem por módulo dos 330 testes automatizados (100% OK)

---

## 🏠 Navegação Externa
- 🚀 [README Principal do Projeto](../README.md)
- 🧪 [Diretório de Testes Automatizados](../tests/)
- ⚙️ [Configurações e Prompts YAML](../configs/prompts/)
- 📊 [Datasets e Dicionário de Dados](../data/)
- 📬 [Coleção Postman v2.1.0](../docs/collections/sprint_mas_postman_collection.json)
