# Prompts Versionados como Código — `configs/prompts/`

> **Armazenamento estruturado, versionado e auditável dos prompts dos agentes cognitivos do Sprint Planning Multi-Agent System (sprint-mas).**

---

## 🏛️ Metodologia e Técnicas de Prompting Utilizadas

Conforme estabelecido nos artigos **WESAAC 2025** e **REIC 2026**, a modelagem e engenharia de prompts dos agentes adota um arcabouço rigoroso e explícito em duas camadas:

### 1. Camada de Elicitação de Requisitos: Metodologia BART
Os papéis, escopos e fronteiras operacionais dos agentes foram elicitados utilizando o **BART (Bot Action and Requirement Template)**, proposto por *Gerstberger, Silva e Guedes (2024)* no *Workshop de Bots (WBots / CSBC)*.

O BART estrutura o comportamento autônomo através de 17 questões fundamentadas em 6 dimensões essenciais:
1. **Persona**: Identidade, arquétipo profissional e tom deliberativo do agente.
2. **Gatilho (Trigger)**: Evento ou transição de estado no LangGraph que dispara a execução do agente.
3. **Pré-condições**: Estado mínimo validado do Blackboard (`SprintState`) antes da ativação do nó.
4. **Ações**: Cadeia determinística e cognitiva de tarefas executadas pelo agente.
5. **Restrições**: Guardrails invioláveis, regras de negócio e restrições de capacidade/skills.
6. **Pós-condições / Objetivo**: Artefato consolidado injetado de volta no `SprintState`.

---

### 2. Camada de Engenharia de Prompt para os LLMs

Para garantir saídas reprodutíveis, sem alucinações e matematicamente consistentes, os prompts aplicam as seguintes técnicas consagradas:

| Técnica | Aplicação Prática no Sistema |
| :--- | :--- |
| **Role-Based Persona Prompting** | Atribuição de papéis hiper-especializados (Product Owner para Priorização, Engineering Allocator para Alocação, Quality Lead para Supervisão). |
| **Constrained / Schema-Enforced** | Forçamento de resposta exclusivamente em formato JSON canônico parseável (`response_format: json_object`), sem introduções conversacionais. |
| **Deterministic Tool-Augmented Context** | Cálculos matemáticos (multiplicação de FTE, soma de story points, ordenação topológica do DAG) são computados por ferramentas Python e injetados prontos no contexto, liberando o LLM do risco de erros aritméticos. |
| **Step-by-Step Deliberation (Zero-Shot CoT)** | Instrução explícita de passos analíticos sequenciais para resolução do problema antes da emissão do artefato final. |
| **Negative Prompting & Guardrails** | Proibições explícitas destacadas em caixa alta (ex: "NUNCA exceda o teto de 0.5 FTE de dev_D", "NUNCA inverta precedências do DAG"). |

---

## 📁 Catálogo de Prompts Versionados

1. [`prioritization.yaml`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/configs/prompts/prioritization.yaml):
   - **Agente**: `prioritization_agent` (Product Owner)
   - **Objetivo**: Ordenação do backlog respeitando dependências causais e valor de negócio.
   - **Placeholders**: `{backlog_json}`, `{topological_order_json}`.

2. [`allocation.yaml`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/configs/prompts/allocation.yaml):
   - **Agente**: `allocation_agent` (Engineering Allocator)
   - **Objetivo**: Mapeamento de tarefas para desenvolvedores, mitigando o gargalo de backend através da realocação de `dev_C` (Fullstack) e respeitando o limite de 0.5 FTE de `dev_D`.
   - **Placeholders**: `{prioritized_tasks_json}`, `{team_json}`, `{capacity_json}`.

3. [`supervisor.yaml`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/configs/prompts/supervisor.yaml):
   - **Agente**: `supervisor_agent` (Quality Lead & Agile Governance)
   - **Objetivo**: Auditoria independente de viabilidade com base nos relatórios determinísticos.
   - **Placeholders**: `{allocations_json}`, `{feasibility_json}`, `{sprint_goal}`.

---

## 🚀 Como Utilizar via Código

```python
from sprint_mas.prompts import load_prompt_yaml, get_agent_prompt_template

# Carregar metadados em dicionário
metadata = load_prompt_yaml("prioritization")
print(f"Técnica: {metadata['technique']}")

# Compilar ChatPromptTemplate pronto para o LangChain / LangGraph
prompt_tpl = get_agent_prompt_template("allocation")
print(prompt_tpl.input_variables)
# Output: ['capacity_json', 'prioritized_tasks_json', 'team_json']
```
