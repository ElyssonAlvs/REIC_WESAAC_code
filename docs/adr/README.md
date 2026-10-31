# 🏛️ Catálogo de Decisões de Arquitetura (ADRs)

> **Registro histórico, imutável e auditável das principais decisões de engenharia, arquitetura de software e governança do projeto Sprint Planning MAS.**

Este diretório segue as boas práticas do formato **MADR (Markdown Architecture Decision Records)** e do nosso **Design System de Engenharia**, garantindo rastreabilidade entre as propostas científicas originais (WESAAC 2025 e REIC 2026) e a implementação em **LangGraph + LangChain + LangSmith**.

---

## 📑 Índice Cronológico de ADRs

| ADR | Título | Data | Status | Resumo da Decisão Técnica |
| :---: | :--- | :---: | :---: | :--- |
| **[0001](./0001-migracao-n8n-para-langgraph.md)** | **Migração do n8n para a Stack LangGraph + LangChain + LangSmith** | 2026-10-02 | `Aprovada` | Substituição da plataforma visual low-code por grafos de estado tipados, cíclicos e testáveis, viabilizando observabilidade e loops de auto-correção. |
| **[0002](./0002-padrao-blackboard-com-pydantic-e-sprintstate.md)** | **Padrão Blackboard para o Estado Multiagente com Pydantic v2 e TypedDict** | 2026-10-02 | `Aprovada` | Centralização do estado compartilhado no `SprintState`, com schemas Pydantic estritos (`Task`, `DeveloperProfile`, `Allocation`) e redutor `add_messages`. |
| **[0003](./0003-fabrica-hibrida-de-llms-groq-e-ollama.md)** | **Fábrica Híbrida de Modelos de Linguagem (Groq e Ollama)** | 2026-10-02 | `Aprovada` | Desacoplamento da camada de LLM via Factory Method, viabilizando desenvolvimento ultra-rápido na nuvem gratuita (Groq) e execução offline (Ollama). |
| **[0004](./0004-padronizacao-de-cenarios-de-teste-e-data-loader.md)** | **Padronização de Cenários de Teste e Data Loader Tipado com Validação de DAG** | 2026-10-19 | `Aprovada` | Ingestão sintética reproduzível dos Cenários A, B e C com algoritmo DFS com coloração tricromática ($O(V+E)$) para garantia de aciclicidade. |
| **[0005](./0005-prompts-como-codigo-e-ferramentas-deterministicas.md)** | **Prompts como Código (Técnica BART) e Ferramentas Determinísticas de Cálculo** | 2026-10-19 | `Aprovada` | Prompts declarativos versionados em YAML (`configs/prompts/*.yaml`), pureza analítica e ferramentas Python puras (`@tool`) com defesas anti-IDOR. |
| **[0006](./0006-agente-priorizacao-hibrido-bart-dag.md)** | **Arquitetura Híbrida Cognitivo-Determinística do Agente de Priorização** | 2026-10-20 | `Aprovada` | Arquitetura em 3 estágios (Tool DAG + LLM BART + Kahn Min-Heap) assegurando matematicamente 0% de erro causal e alinhamento estrito ao paper. |

---

## 🎯 Estrutura Padrão de uma ADR

Cada documento de decisão segue a anatomia:
1. **Cabeçalho:** Número, Título, Data da Proposta, Data de Homologação, Status e Autoria.
2. **Contexto & Forças:** Cenário técnico, problema identificado no n8n e requisitos invariantes do paper (ex: 0% de erro causal, teto de 0.5 FTE de dev_D).
3. **Decisão:** Descrição minuciosa da abordagem escolhida e diagramas Mermaid.
4. **Matriz de Estados & Comportamentos:** Tabela exaustiva mapeando inputs válidos, cenários de borda e respostas determinísticas.
5. **Diretrizes (Do's & Don'ts):** Recomendações práticas para engenheiros e mantenedores.
6. **Consequências:** Impactos positivos (benefícios obtidos) e negativos (trade-offs assumidos).
7. **Rastreabilidade Científica & Validação:** Vínculos diretos com seções dos artigos WESAAC 2025 / REIC 2026 e cobertura da suíte de testes.

---

## 🔗 Navegação Rápida
- 📚 [Artigos Científicos de Referência](../papers/README.md)
- 🎓 [Guia de Aprendizado e Teoria](../guides/GUIA_APRENDIZADO.md)
- 📋 [System Card do Sistema](../system-card.md)
- 🏠 [Voltar para o README Principal](../../README.md)
