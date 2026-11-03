# Guia de Aprendizado: Sprint Planning Multi-Agent System (MAS)

> **Documento didático, conceitual e de referência arquitetural para a reimplementação da arquitetura de agentes dos artigos WESAAC (2025) e REIC (2026) na stack LangGraph + LangChain + LangSmith.**

---

## 🧭 Sumário

1. [Visão Geral & Por Que Reimplementar o Artigo?](#1-visão-geral--por-que-reimplementar-o-artigo)
2. [Matriz Comparativa: Por Que o n8n Não Foi Suficiente?](#2-matriz-comparativa-por-que-o-n8n-não-foi-suficiente)
3. [Teoria de Sistemas Multiagentes: BDI e Padrão Blackboard](#3-teoria-de-sistemas-multiagentes-bdi-e-padrão-blackboard)
4. [Anatomia Técnica do `SprintState` e Esquemas de Domínio](#4-anatomia-técnica-do-sprintstate-e-esquemas-de-domínio)
5. [Arquitetura Desacoplada de LLMs (Fábrica Groq + Ollama)](#5-arquitetura-desacoplada-de-llms-fábrica-groq--ollama)
6. [Orquestração Cíclica, Nó Corretivo & Circuit Breaker (LangGraph)](#6-orquestração-cíclica-nó-corretivo--circuit-breaker-langgraph)
7. [Catálogo de Decisões de Arquitetura (ADRs)](#7-catálogo-de-decisões-de-arquitetura-adrs)
8. [Laboratório Prático: Como Testar e Inspecionar o Código](#8-laboratório-prático-como-testar-e-inspecionar-o-código)

---

## 1. Visão Geral & Por Que Reimplementar o Artigo?

No artigo original da **REIC 2026** (*Metodologia Ágil e IA em Sistemas Multiagentes: Avaliação Experimental de uma Arquitetura para Planejamento e Execução de Sprints*), propôs-se uma arquitetura baseada na plataforma visual **n8n**.

Embora o artigo tenha demonstrado o valor do planejamento assistido por agentes cognitivos (reduzindo a sobrecarga humana de ~12 minutos para segundos), a validação empírica revelou fragilidades intrínsecas ao uso de ferramentas *low-code*:
- **Falta de rigor empírico em dados reais:** No n8n, os nós foram configurados com entradas de teste perfeitas. Ao lidar com exceções, dependências cíclicas ou regras de negócio granulares, a plataforma carece de garantias de tipo em tempo de execução.
- **Dificuldade de controle de fluxo cíclico:** O processo de Sprint Planning não é estritamente sequencial. Se a alocação proposta por um agente de IA violar a capacidade máxima (FTE) de um desenvolvedor, o sistema precisa **rejeitar o plano e forçar um loop deliberativo de correção**. No n8n, loops complexos com estado distribuído são frágeis e suscetíveis a loops infinitos ou *timeouts*.

**A meta da reimplementação com LangGraph:**
Construir uma prova de conceito **100% auditável, baseada em código Python puro**, com testes unitários automatizados, validação formal de restrições e rastreabilidade total de raciocínio via **LangSmith**.

---

## 2. Matriz Comparativa: Por Que o n8n Não Foi Suficiente?

| Dimensão Técnica | Abordagem Anterior (n8n) | Abordagem Atual (LangGraph) |
| :--- | :--- | :--- |
| **Contrato de Dados** | JSON não tipado passado como *payload* HTTP entre nós. | `SprintState` baseado em **Pydantic v2** e **TypedDict** com checagem estrita de tipos e restrições. |
| **Padrão de Agentes** | Nós individuais disparando requisições Webhook ponta a ponta. | **Padrão Blackboard**, onde todos os nós leem e escrevem em um estado compartilhado. |
| **Loops e Auto-correção** | Tratamento de erros rudimentar; loops condicionais complexos são difíceis de controlar. | **Arestas condicionais nativas** (`conditional_edges`) que roteiam o fluxo de volta ao agente causador de inconsistências. |
| **Validação de Regras** | Delegada integralmente à LLM, sujeita a alucinações de FTE. | **Validação determinística em código Python puro** combinada com deliberação semântica da LLM. |
| **Versionamento e Testes** | JSON de workflow visual, difícil de versionar e testar em CI/CD. | Código fonte modular em Python com suíte completa de **pytest** e mocks de rede. |
| **Observabilidade** | Histórico básico de execuções no painel do n8n. | **LangSmith**: telemetria de latência, contagem de tokens, árvore de chamadas e traces de cada nó. |

---

## 3. Teoria de Sistemas Multiagentes: BDI e Padrão Blackboard

### 3.1. O Modelo BDI (Belief–Desire–Intention)
A literatura clássica de agentes (Rao & Georgeff, 1995; Wooldridge, 2002) modela entidades racionais com base em três pilares, que agora encontram correspondência direta no código:

```mermaid
flowchart TD
    subgraph BDI["Mapeamento BDI no LangGraph"]
        B["Beliefs (Crenças)\nEstado do mundo: Backlog, Equipe, Restrições de FTE"]
        D["Desires (Desejos)\nMetas de negócio elicitadas pela técnica BART"]
        I["Intentions (Intenções)\nPlanos deliberados pelos nós de LLM no Grafo"]
    end

    B -->|Informa| I
    D -->|Guia| I
    I -->|Ação via Nós / Tools| B
```

- **Crenças (*Beliefs*):** É a percepção do ambiente mantida pelo agente. No nosso código, está no `SprintState["backlog"]` e `SprintState["team"]`.
- **Desejos (*Desires*):** São os objetivos globais da sprint definidos pelo Product Owner e codificados nos *system prompts* guiados pelas regras BART.
- **Intenções (*Intentions*):** São os compromissos de ação adotados pelo sistema, concretizados em `SprintState["allocations"]` e `SprintState["sprint_plan"]`.
- **Função de Consistência e Verificação BDI ($V: \mathcal{I} \times \mathcal{B} \to \{\text{valid}, \text{invalid}\}$):** É o papel desempenhado pelo **Agente Validador Determinístico** (`validator.py`). Ele atua como o juiz formal que audita se as intenções candidatas geradas pelos agentes cognitivos cumprem estritamente as crenças do ambiente (tetos de FTE, precedências do DAG e compatibilidade de skills) sem consumir tokens nem depender de inferências probabilísticas. Se inválidas, preenche `validation_errors`, instruindo o Supervisor a redirecionar o ciclo BDI.
- **Ciclo Percepção-Ação & Replanejamento BDI:** Concretizado na orquestração cíclica do LangGraph (`graph.py`), onde o Agente Supervisor coordena a deliberação dos agentes e, perante inconsistências, aciona o nó de auto-ajuste (`corrective_replan_node`) para podar o escopo e recalibrar as alocações até a convergência formal.

---

### 3.2. O Padrão Arquitetural Blackboard
O padrão **Blackboard** (Corkill, 1991; Jennings, 2000) resolve o problema de cooperação entre especialistas heterogêneos:

```mermaid
flowchart LR
    subgraph Blackboard["Quadro-Negro Central (SprintState)"]
        direction TB
        B1["Backlog de Tarefas"]
        B2["Perfis de Equipe & FTE"]
        B3["Tarefas Priorizadas"]
        B4["Alocações Propostas"]
        B5["Erros de Validação"]
        B6["Histórico de Mensagens (add_messages)"]
    end

    AgPO["Agente Priorização\n(Ordena por Valor/Dependência)"] <--> Blackboard
    AgAlloc["Agente Alocação\n(Match Semântico Skill↔FTE)"] <--> Blackboard
    AgVal["Agente Validação\n(Python Puro: Checa Regras)"] <--> Blackboard
```

1. **Quadro Negro (`SprintState`):** O espaço de memória compartilhado onde o estado do planejamento é construído incrementalmente.
2. **Fontes de Conhecimento (Agentes Especialistas):** Agentes com papéis únicos (Priorização, Alocação, Validação) que inspecionam o quadro e realizam contribuições direcionadas.
3. **Mecanismo de Controle (Supervisor / Grafo):** A máquina de estados finitos do LangGraph que decide qual especialista atua a cada momento.

---

## 4. Anatomia Técnica do `SprintState` e Esquemas de Domínio

No arquivo [`sprint_mas/state.py`](../../sprint_mas/state.py), construímos contratos de dados estritos com **Pydantic v2**:

### 4.1. Modelos de Domínio
- **`Task`**: Representa um item de trabalho do backlog.
  - `id`: Identificador único (ex: `TSK-101`).
  - `title` e `description`: Conteúdo da demanda.
  - `story_points`: Esforço estimado (`int > 0` obrigatório — previne pontos nulos ou negativos).
  - `skill_required`: Habilidade técnica requerida (ex: `backend`, `frontend`, `devops`).
  - `priority`: Valor de 1 (máxima) a 5 (mínima).
  - `dependencies`: Lista de IDs de tarefas predecessoras que precisam ser concluídas antes.
- **`DeveloperProfile`**: Representa o perfil de um membro do time.
  - `id`: Identificador (ex: `dev_B`).
  - `name`: Nome do desenvolvedor.
  - `skills`: Conjunto de habilidades dominadas.
  - `fte`: Fração de dedicação (`0.0 <= fte <= 1.0` obrigatório — previne alocações além da jornada real).
- **`Allocation`**: Mapeamento de atribuição de uma tarefa para um desenvolvedor, acompanhado da justificativa gerada pela IA.
- **`SprintPlan`**: Artefato final consolidado da sprint.

### 4.2. O Redutor de Mensagens (`add_messages`)
No `SprintState`, o campo de mensagens utiliza o redutor:
```python
messages: Annotated[list[BaseMessage], add_messages]
```
**Por que isso é fundamental?**  
Em nós de grafos com estado, se você simplesmente atribuir uma nova lista de mensagens, você **sobrescreve** o histórico anterior. O redutor `add_messages` instrui o LangGraph a **concatenar** novas mensagens ao histórico existente, garantindo rastreabilidade deliberativa completa.

---

## 5. Arquitetura Desacoplada de LLMs (Fábrica Groq + Ollama)

Em [`sprint_mas/llm_factory.py`](../../sprint_mas/llm_factory.py), aplicou-se o padrão de projeto **Factory Method**:

```mermaid
flowchart TD
    Client["Agente LangGraph (Nó)"] -->|get_llm()| Factory["LLM Factory"]
    Factory -->|PROVIDER=groq| Groq["ChatGroq\n(llama-3.1-8b-instant na nuvem)"]
    Factory -->|PROVIDER=ollama| Ollama["ChatOllama\n(llama3:latest local offline)"]
```

### Vantagens Práticas:
1. **Desenvolvimento Veloz com Groq:** Acesso gratuito à inferência via LPU da Groq (~14.400 requisições/dia), permitindo iterações em frações de segundo.
2. **Execução Segura e Offline com Ollama:** Fallback local sem necessidade de conexão com a internet ou dependência de chaves de API externas.
3. **Isolamento de Testes:** Nos testes automatizados (`tests/test_llm_factory.py`), a fábrica é testada com mocks, garantindo 100% de cobertura sem custo de tokens.

---

## 6. Orquestração Cíclica, Nó Corretivo & Circuit Breaker (LangGraph)

No módulo [`sprint_mas/graph.py`](../../sprint_mas/graph.py), o fluxo multiagente é compilado como um `StateGraph(SprintState)` cíclico, superando a linearidade frágil do n8n:

```mermaid
flowchart TD
    START(["START"]) --> P["prioritizer<br/>(Product Owner BART)"]
    P --> A["allocator<br/>(Alocação de Recursos)"]
    A --> V["validator<br/>(Auditoria 5D Zero LLM)"]
    V --> Route{"route_after_validation<br/>Circuit Breaker (max_retries=2)"}
    Route -->|Violações && tentativas <= max_retries| R["replan<br/>(corrective_replan_node)"]
    R -->|Reset allocations: []| A
    Route -->|Sem violações OU tentativas esgotadas| S["supervisor<br/>(Governança & Server Authority)"]
    S --> END(["END"])
```

### 6.1. O Algoritmo de Seleção Viável (`select_feasible_sprint_tasks`)
Em cenários de sobrecarga (como o Cenário B, onde o backlog possui 128 pts para uma capacidade máxima de 84 pts), o nó `corrective_replan_node` invoca a seleção algorítmica `select_feasible_sprint_tasks`:
1. **Preservação de Causalidade DAG:** Tarefas filhas só podem ser agendadas se 100% de suas dependências causais estiverem no subconjunto selecionado.
2. **Respeito aos Tetos FTE:** O algoritmo simula a distribuição gulosa determinística garantindo que nenhum desenvolvedor ultrapasse seu teto individual (`dev_D <= 10.0 pts`, `dev_B <= 14.0 pts`) e que a carga global respeite os 84 pts.
3. **Reset de Alocações:** Ao podar o escopo, redefine `allocations = []`, permitindo que o `allocator` recalibre perfeitamente o subconjunto na segunda passagem (resolvendo o Cenário B em 2-pass sem intervenção humana).

### 6.2. Circuit Breaker Stateless Anti-Loop Infinito
A função de roteamento condicional `route_after_validation(state, max_retries=2)` implementa um disjuntor sem estado persistido:
- Analisa a janela deliberativa de mensagens compartilhadas (`messages`) contando quantas vezes o validador executou desde a última priorização.
- Se `attempts <= max_retries`, autoriza o ciclo corretivo em `replan`.
- Se `attempts > max_retries`, desvia compulsoriamente para o `supervisor`, que emite a rejeição executiva limpa, eliminando qualquer risco de `GraphRecursionError`.

### 6.3. Isolamento Concorrente por Sessão (`MemorySaver`)
Com `MemorySaver` configurado via `thread_id` (`config={"configurable": {"thread_id": "sessao_123"}}`), múltiplas instâncias de sprints podem ser executadas em paralelo sob multithreading sem colisões no Blackboard compartilhado.

---

## 7. Catálogo de Decisões de Arquitetura (ADRs)

Todas as escolhas estruturais da migração do n8n para LangGraph estão formalizadas e catalogadas em [`docs/adr/`](../adr/README.md):

1. **[ADR 0001: Migração do n8n para LangGraph](../adr/0001-migracao-n8n-para-langgraph.md)** — Substituição do motor visual por grafos cíclicos de estado tipados.
2. **[ADR 0002: Padrão Blackboard com Pydantic v2](../adr/0002-padrao-blackboard-com-pydantic-e-sprintstate.md)** — `SprintState` centralizado com validações de fronteira e redutor `add_messages`.
3. **[ADR 0003: Fábrica Híbrida de LLMs (Groq + Ollama)](../adr/0003-fabrica-hibrida-de-llms-groq-e-ollama.md)** — Desacoplamento da camada de inferência para nuvem rápida e execução offline.
4. **[ADR 0004: Ingestão de Dados e Validação de DAG](../adr/0004-padronizacao-de-cenarios-de-teste-e-data-loader.md)** — Algoritmo DFS com coloração tricromática ($O(V+E)$) para prevenção de ciclos.
5. **[ADR 0005: Prompts BART e Ferramentas Determinísticas](../adr/0005-prompts-como-codigo-e-ferramentas-deterministicas.md)** — Prompts declarativos em YAML e ferramentas Python puras (`@tool`) com defesas anti-IDOR.
6. **[ADR 0006: Priorizador Híbrido Cognitivo-Determinístico](../adr/0006-agente-priorizacao-hibrido-bart-dag.md)** — Arquitetura em 3 estágios assegurando 0% de erro causal via fallback de Kahn min-heap.
7. **[ADR 0007: Alocador de Recursos e Resolução de Gargalos via Perfil Fullstack](../adr/0007-agente-alocacao-capacidade-skills.md)** — Arquitetura híbrida em 3 estágios com mitigação de gargalo via `dev_C` e blindagem do teto de 0.5 FTE de `dev_D`.
8. **[ADR 0008: Agente Validador Determinístico Multi-Dimensional](../adr/0008-agente-validador-deterministico-zero-llm.md)** — Auditoria determinística em 5 dimensões (Zero LLM, latência sub-milissegundo, Server Authority e detecção de ciclos DFS tricolor).
9. **[ADR 0009: Orquestração Cíclica com Grafo LangGraph, Nó Corretivo de Escopo e Circuit Breaker](../adr/0009-orquestracao-ciclica-supervisor-langgraph-circuit-breaker.md)** — Topologia cíclica do StateGraph, corte determinístico de escopo por capacidade (`select_feasible_sprint_tasks`), Circuit Breaker stateless anti-loop infinito e Server Authority no supervisor.

---

## 8. Laboratório Prático: Como Testar e Inspecionar o Código

### 8.1. Executando a Suíte Completa de Testes
Para certificar a integridade do código em seu terminal:
```bash
uv sync
uv run pytest tests/ -v
```
*Status esperado: 125 testes automatizados aprovados (100% OK).*

### 8.2. Testando Validações de Borda (Edge Cases)
Experimente instanciar um objeto `DeveloperProfile` com FTE inválido no console Python:
```python
from sprint_mas.state import DeveloperProfile

# Isso disparará imediatamente um ValidationError explicativo:
try:
    dev = DeveloperProfile(id="dev_X", name="Invalido", skills=["backend"], fte=1.5)
except Exception as e:
    print("Rejeição esperada:", e)
```
Essa segurança de tipos em tempo de execução é o que garante que a LLM não corromperá o planejamento durante a execução do grafo.

### 8.3. Testando a Auditoria Determinística (Zero LLM)
Experimente auditar um estado com sobrecarga de FTE no console Python:
```python
from sprint_mas.agents.validator import audit_sprint_state
from sprint_mas.state import Allocation, DeveloperProfile, Task

team = [DeveloperProfile(id="dev_D", name="Dev D", skills=["backend"], fte=0.5)]
tasks = [
    Task(id="TSK-1", title="A", description="Task A", story_points=8, skill_required="backend", priority=1),
    Task(id="TSK-2", title="B", description="Task B", story_points=5, skill_required="backend", priority=2),
]
allocations = [
    Allocation(task_id="TSK-1", developer_id="dev_D", allocated_points=8),
    Allocation(task_id="TSK-2", developer_id="dev_D", allocated_points=5),
]

report = audit_sprint_state({"team": team, "prioritized_tasks": tasks, "allocations": allocations})
print("Válido?", report.is_valid)  # False (13 pts > 10 pts máx de 0.5 FTE)
print("Violações:", report.violations)
```
O validador calcula a violação instantaneamente (< 0.2ms) sem gastar nenhum token, garantindo a integridade dos dados antes da homologação final da sprint.

### 8.4. Testando a Execução Ponta a Ponta com Auto-Ajuste Cíclico (`run_sprint_planning`)
Experimente executar o pipeline completo com corte de escopo automático e circuit breaker:
```python
from sprint_mas.data_loader import load_scenario
from sprint_mas.graph import run_sprint_planning

# Carrega o Cenário B (30 tarefas = 128 pts, capacidade = 84 pts)
scenario_b = load_scenario("scenario_b.json")
result = run_sprint_planning(
    backlog=scenario_b["tasks"],
    team=scenario_b["team"],
    thread_id="lab_sprint_b",
    sprint_goal="Entregar itens prioritários com auto-ajuste de capacidade.",
)

# O grafo executa 2 passagens (auto-correção) e homologa o plano viável:
plan = result["sprint_plan"]
print("Status:", "APROVADO" if plan else "REJEITADO")
print("Pontos Alocados:", plan.total_points)  # Rigorosamente <= 84 pts
print("Tarefas Agendadas:", len(plan.tasks))
```
Esse laboratório demonstra a convergência automática em 2 passagens, onde tarefas de menor prioridade ou excedentes são descartadas matematicamente sem travar o motor multiagente.

