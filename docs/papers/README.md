# 📚 Trabalhos Científicos de Referência (Papers)

> **Acervo de publicações científicas e transcrições textuais que fundamentam a teoria, modelagem conceitual e validação empírica deste repositório.**

Este projeto é uma reimplementação robusta, tipada e auditável baseada na produção científica desenvolvida por pesquisadores da **Universidade Federal do Ceará (UFC) — Campus Quixadá**.

---

## 📑 1. Artigos Publicados

### 1.1 WESAAC 2025 (Concepção Teórica & Modelo BDI)
- **Título Completo:** *Agile Methodology and AI in Multi-Agent Systems: An agent for planning and executing sprints*
- **Veículo:** 19º Workshop-Escola de Sistemas de Agentes, seus Ambientes e Aplicações (WESAAC 2025)
- **Instituição:** Universidade Federal do Ceará (UFC), Campus Quixadá
- **Resumo:** Apresenta a modelagem inicial de uma arquitetura baseada em agentes cognitivos para automação da cerimônia de *Sprint Planning* no framework Scrum. Mapeia as entidades ágeis para o modelo clássico **BDI (Belief–Desire–Intention)**: o estado das tarefas e equipe como *Crenças*, metas de negócio como *Desejos* e o plano de sprint final como *Intenções*.
- **Arquivos Locais:**
  - 📕 Artigo em PDF: [`WESAAC_2025_Agile_MultiAgent.pdf`](./WESAAC_2025_Agile_MultiAgent.pdf)
  - 📄 Transcrição Textual Completa: [`wesaac_text.txt`](./wesaac_text.txt)

---

### 1.2 REIC 2026 (Avaliação Experimental & Comparativo Empírico)
- **Título Completo:** *Metodologia Ágil e IA em Sistemas Multiagentes: Avaliação Experimental de uma Arquitetura para Planejamento e Execução de Sprints*
- **Veículo:** Revista Eletrônica de Iniciação Científica em Computação (REIC), Sociedade Brasileira de Computação (SBC), 2026
- **Instituição:** Universidade Federal do Ceará (UFC), Campus Quixadá
- **Resumo:** Conduz uma rigorosa avaliação experimental comparando o método tradicional manual (**M-Manual**) versus o método assistido por agentes cognitivos (**M-Agente**). Demonstra redução drástica do tempo de planejamento de sprints (de ~765 segundos para segundos), mantendo alta aderência de capacidade. Identifica empiricamente as limitações de plataformas visuais *low-code* (como o n8n) em garantir aciclicidade estrita em DAGs e respeitar limites fracionados de FTE, motivando a presente migração para a stack **LangGraph + LangChain + Pydantic v2**.
- **Arquivos Locais:**
  - 📕 Artigo em PDF: [`REIC_2026_Metodologia_Agil_Multiagentes.pdf`](./REIC_2026_Metodologia_Agil_Multiagentes.pdf)
  - 📄 Transcrição Textual Completa: [`reic_text.txt`](./reic_text.txt)

---

## 🎯 2. Como os Artigos se Relacionam com a Arquitetura LangGraph

| Dimensão Científica | Artigo de Origem | Realização Técnica no Repositório |
| :--- | :---: | :--- |
| **Padrão Blackboard** | WESAAC 2025 / REIC 2026 | `SprintState` em [`sprint_mas/state.py`](../../sprint_mas/state.py) com Pydantic v2 e TypedDict. |
| **Cenários A, B e C** | REIC 2026 (Seção 5) | Datasets sintéticos tipados em [`data/processed/`](../../data/processed/) validados por [`sprint_mas/data_loader.py`](../../sprint_mas/data_loader.py). |
| **0% de Erro Causal** | REIC 2026 (Seção 6.1) | Algoritmo de Kahn ponderado com min-heap e `@tool get_topological_order` em [`sprint_mas/agents/prioritizer.py`](../../sprint_mas/agents/prioritizer.py). |
| **Teto de FTE (dev_D 0.5)**| REIC 2026 (Seção 5.2) | Validação determinística estrita e `@tool check_allocation_feasibility` em [`sprint_mas/tools.py`](../../sprint_mas/tools.py). |
| **Framework BART** | Gerstberger et al. / Papers | Prompts versionados em YAML com elicitação formal em [`configs/prompts/`](../../configs/prompts/). |

---

## 🔗 Navegação Rápida
- 🏛️ [Catálogo de Decisões Arquiteturais (ADRs)](../adr/README.md)
- 🎓 [Guia de Aprendizado e Teoria](../guides/GUIA_APRENDIZADO.md)
- 📋 [System Card](../system-card.md)
- 🏠 [Voltar para o README Principal](../../README.md)
