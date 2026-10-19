# System Card — Sprint Planning Multi-Agent System (MAS)

> **Documento técnico padronizado de governança, limitações, riscos e escopo operacional do sistema de agentes inteligentes.**

---

## 1. Visão Geral do Sistema
- **Nome:** Sprint Planning Multi-Agent System (sprint-mas)
- **Versão:** 0.1.0
- **Base Teórica:** Artigos WESAAC 2025 e REIC 2026 (UFC Quixadá)
- **Stack Tecnológica:** Python 3.12, LangGraph, LangChain, Pydantic v2, Groq (`llama-3.1-8b-instant`), Ollama (`llama3:latest`).

---

## 2. Finalidade Pretendida (Intended Use)
- **Objetivo Primário:** Auxiliar Scrum Masters e Product Owners na cerimônia de planejamento de sprint (*Sprint Planning*), automatizando o cruzamento entre backlog de tarefas, valor de negócio, dependências encadeadas e restrições de capacidade/especialidade da equipe.
- **Público Alvo:** Times de engenharia de software ágil que utilizam o framework Scrum.
- **Modo de Operação:** Co-piloto deliberativo (o sistema propõe e valida o plano de sprint, mas a aprovação final pertence aos líderes humanos da equipe).

---

## 3. Agentes Especialistas e Arquitetura do Grafo
O sistema opera como uma sociedade de agentes colaborativos estruturada em torno de um **Blackboard** (`SprintState`):
1. **Agente Supervisor:** Orquestra o fluxo de execução, interpreta comandos em linguagem natural e direciona para os agentes especialistas.
2. **Agente de Priorização:** Analisa itens do backlog com base em valor de negócio, dependências lógicas e regras da técnica **BART**.
3. **Agente de Alocação:** Realiza o casamento semântico entre a habilidade exigida pela tarefa (`backend`, `frontend`, etc.) e a disponibilidade fracionada (FTE) dos desenvolvedores.
4. **Agente de Validação (Determinístico):** Executa regras matemáticas e lógicas em Python puro (sem LLM) para barrar alucinações de sobrecarga de capacidade ou dependências violadas.

---

## 4. Limitações Conhecidas
- **Dependência de Esquema Estruturado:** O sistema atinge sua máxima eficácia quando as tarefas possuem títulos, descrições e estimativas de esforço preliminares definidas.
- **Capacidade Fracionada (FTE):** O modelo opera com frações entre `0.0` e `1.0`. Variações imprevisíveis de saúde ou licenças durante a sprint requerem reexecução do grafo com novos inputs.
- **Janela de Contexto de Modelos Leves:** Para modelos de 8B (como Llama 3.1 8B), o backlog deve ser preferencialmente agrupado em lotes de até 50 tarefas para manter precisão de atenção nas dependências.

---

## 5. Riscos e Mitigações de Segurança

| Risco Identificado | Severidade | Estratégia de Mitigação Implementada |
| :--- | :---: | :--- |
| **Alucinação de Capacidade:** A LLM alocar 150% do tempo de um dev. | Alta | **Validação em Schema Pydantic:** Campo `fte` restrito a `[0.0, 1.0]` e validador determinístico em Python puro. |
| **Ciclo de Dependência Inválido:** Agendar tarefa filha antes da tarefa pai. | Alta | **Grafo Acíclico Dirigido (DAG):** Verificação algorítmica de precedência de nós antes da confirmação do plano. |
| **Vazamento de Credenciais:** Envio acidental de chaves de API. | Crítica | Arquivo `.env` protegido via `.gitignore` e separação estrita de variáveis de ambiente. |
| **Falha de Conectividade Externa:** Queda da API da Groq. | Média | **Fábrica Híbrida Desacoplada:** Fallback imediato para Ollama local sem alteração de código. |

---

## 6. Governança e Métricas de Avaliação
O sistema é avaliado nas seguintes métricas objetivas (reproduzindo os cenários do paper):
- **Taxa de Conformidade Lógica:** % de dependências respeitadas (meta: 100%).
- **Taxa de Alocação de Capacidade:** % de desenvolvedores dentro de seus limites de FTE (meta: 100%).
- **Latência de Planejamento:** Tempo decorrido entre o gatilho inicial e o plano final validado (meta: < 10 segundos).
- **Rastreabilidade:** 100% das execuções telemetradas via LangSmith.
