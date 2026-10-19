# ADR 0001: Migração de Arquitetura Low-Code (n8n) para Código Puro com LangGraph

- **Status:** Aceito
- **Data:** 2026-10-02
- **Decisores:** Elysson Alves de Lacerda (Tech Lead), Antigravity (Tech Manager)
- **Contexto Técnico:** Reimplementação do Sistema Multiagente (SMA) dos artigos WESAAC 2025 e REIC 2026.

---

## Contexto e Forças Impulsionadoras

No artigo original da REIC 2026 (*Metodologia Ágil e IA em Sistemas Multiagentes*), o sistema foi orquestrado utilizando nós visuais e webhooks na plataforma low-code **n8n**.

Embora o n8n tenha permitido um protótipo conceitual inicial rápido, foram identificadas fragilidades técnicas graves que impediam sua viabilidade em produção e sua validação empírica rigorosa:
1. **Ausência de Type-Safety:** Dados trafegavam como objetos JSON dinâmicos sem validação estrita de esquemas em tempo de execução.
2. **Loops e Auto-correção Limitados:** O planejamento de sprint envolve raciocínio não linear (quando uma alocação falha por FTE, deve-se rejeitar e forçar re-deliberação). No n8n, grafos cíclicos complexos com estado distribuído são frágeis e propensos a timeouts ou loops infinitos.
3. **Impossibilidade de Testes Unitários com Mocks:** O n8n não permitia isolar nós em suítes determinísticas como o `pytest`.
4. **Acoplamento a Ferramenta Visual:** Dificuldade de versionamento de código via Git e integração em pipelines de CI/CD.

---

## Decisão

Adotamos a biblioteca **LangGraph** (combinada com **LangChain** e **LangSmith**) em substituição ao n8n.

1. O fluxo passa a ser modelado como um **StateGraph** compilado em Python 3.12.
2. O estado é gerido centralmente por uma estrutura tipada (`SprintState`).
3. As decisões de transição entre nós são governadas por arestas condicionais determinísticas (`conditional_edges`).
4. Toda a observabilidade de chamadas de LLM, latência e tokens é direcionada para o **LangSmith**.

---

## Consequências

### Positivas
- **Controle Fino do Ciclo de Vida:** O grafo suporta loops corretivos e controle formal de paradas.
- **Testabilidade:** Suporte a mocks de LLM e cobertura de 100% via `pytest` sem custo de tokens em CI/CD.
- **Rastreabilidade Científica:** Cada execução pode ser auditada de ponta a ponta com traces imutáveis no LangSmith.

### Negativas / Mitigações
- **Curva de Aprendizado Maior:** Exige conhecimento de grafos de estado, Pydantic e programação assíncrona em Python (mitigado pelo `GUIA_APRENDIZADO.md`).
- **Sem Interface Gráfica Pronta:** A visualização de nós passa a ser gerada via mermaid ou studio do LangGraph, ao invés do canvas arrasta-e-solta do n8n.
