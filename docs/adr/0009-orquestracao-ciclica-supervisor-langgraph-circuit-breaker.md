# ADR 0009: Orquestração Cíclica com Grafo LangGraph, Nó Corretivo de Escopo e Circuit Breaker Stateless

## 1. Status & Metadados
- **Status:** Aprovada (Homologada em 2026-11-02 pelo Security & QA Auditor)
- **Decisores:** Tech Lead (Elysson Alves de Lacerda), Tech Manager (Antigravity), Cautious Coder
- **Data da Proposta:** 2026-11-02
- **Data de Homologação:** 2026-11-02
- **Vínculo Científico:** WESAAC 2025 (Seção 4) e REIC 2026 (Seções 2.3, 3.2, 4 e 4.1)

---

## 2. Contexto & Forças Motivadoras

Nos trabalhos fundacionais de planejamento ágil assistido por Sistemas Multiagentes (SMA) (WESAAC 2025; REIC 2026), a deliberação de uma sprint Scrum não é um pipeline linear unidirecional (*feedforward*), mas um processo reflexivo com retroalimentação contínua sujeito a limites materiais de capacidade e restrições formais:

1. **Inviabilidade Estrutural de Backlogs Reais em Passagem Única (Excedente de Capacidade):**
   Em cenários do mundo real e especificamente no **Cenário B** avaliado no artigo REIC 2026 (Seção 5.1), o backlog de produto submetido ao planejamento possui **128 Story Points** (30 itens de trabalho), enquanto a capacidade máxima analítica da equipe em uma sprint de 10 dias úteis totaliza rigorosamente **84 Story Points** ($20 + 14 + 20 + 10 + 20$). Um fluxo linear sem poda de escopo ou sem ciclo de retroalimentação inevitavelmente aloca tarefas excedentes, gerando violações severas de sobrecarga de FTE (`dev_D > 10.0 pts`, `dev_B > 14.0 pts`) que colapsam a validação.
2. **Risco Crítico de Loop Infinito e `GraphRecursionError` em Grafos Cíclicos:**
   A introdução de arestas de retroalimentação entre validação e replanejamento cria o risco iminente de ciclos infinitos não convergentes caso o estado continue inválido. Sem um mecanismo estrito de *Circuit Breaker*, a pilha do interpretador LangGraph atinge o `recursion_limit` lançando `GraphRecursionError`, provocando queda abrupta do serviço (*service crash*) e indisponibilidade do sistema.
3. **Isolamento de Estado Concorrente por Sessão (*Session Isolation*):**
   Múltiplas sprints de diferentes squads ou cenários concorrentes de simulação demandam execução simultânea sem contaminação cruzada de memória compartilhada (*cross-talk*). A arquitetura deve fornecer isolamento transacional estrito baseado em identificadores de sessão (`thread_id`) via *checkpointer* em memória.
4. **Consolidação Formal das Intenções BDI e Server Authority Inviolável:**
   Segundo a semântica BDI formal (REIC 2026, Seção 2.3), o artefato executável `SprintPlan` (Intenção) somente pode ser materializado e homologado se o plano auditado atender a 100% dos invariantes de domínio. Sob o princípio *Zero Trust* e *Server Authority*, o Agente Supervisor jamais pode confiar cegamente em deliberações de LLMs probabilísticos que possam alucinar `is_approved = True` diante de relatórios com violações ativas.

---

## 3. Decisão Técnica Adotada

Adotamos a orquestração do Sistema Multiagente via **Grafo de Estados Cíclico do LangGraph** ([`sprint_mas/graph.py`](../../sprint_mas/graph.py)) coordenado pelo **Agente Supervisor de Governança & Qualidade** ([`sprint_mas/agents/supervisor.py`](../../sprint_mas/agents/supervisor.py)), ancorado em quatro pilares arquiteturais:

```mermaid
flowchart TD
    START(["START"]) --> P["prioritizer<br/>(Product Owner BART + DAG)"]
    P --> A["allocator<br/>(Resource Allocator BART + Skills)"]
    A --> V["validator<br/>(5D Deterministic Audit Zero LLM)"]
    
    V --> Route{"route_after_validation<br/>Circuit Breaker (max_retries=2)"}
    
    Route -->|Violações &&<br/>tentativas <= max_retries| R["replan<br/>(corrective_replan_node:<br/>select_feasible_sprint_tasks)"]
    R -->|Reset allocations: []<br/>Escopo Viável <= 84 pts| A
    
    Route -->|Sem violações (0 erros)<br/>OU tentativas > max_retries| S["supervisor<br/>(BART Deliberation +<br/>Server Authority Guard)"]
    
    S --> END(["END<br/>(SprintPlan consolidado ou rejeitado)"])
```

### 3.1 Nó Corretivo Determinístico e Seleção Viável de Escopo (`select_feasible_sprint_tasks`)
Ao detectar violações no plano preliminar (ex: estouro de capacidade na primeira passagem do Cenário B com 128 pts), o fluxo desvia para o nó `replan` (`corrective_replan_node`), que executa a seleção algorítmica pura `select_feasible_sprint_tasks`:
- Percorre a lista de tarefas respeitando estritamente a precedência topológica de dependências causais ($pos[dep] < pos[task]$).
- Incorpora uma tarefa candidata apenas se **todas** as suas dependências já tiverem sido selecionadas.
- Simula a alocação gulosa determinística garantindo que nenhum desenvolvedor ultrapasse seu teto analítico de FTE (`calculate_team_capacity`) e que a carga total não exceda a capacidade da equipe (84 pts no Cenário B).
- Efetua o reset atômico das alocações (`allocations: []`), forçando o `allocator` a redistribuir exclusivamente o subconjunto viável de tarefas no segundo ciclo.

### 3.2 Circuit Breaker Stateless Anti-Loop Infinito (`route_after_validation`)
A aresta condicional pós-validação implementa um disjuntor de segurança stateless:
- Inspeciona a lista imutável `validation_errors`: se vazia, roteia imediatamente para `supervisor`.
- Em presença de violações, contabiliza na janela corrente de deliberação (`messages`) o número de execuções do validador desde a última priorização.
- Se `validator_attempts <= max_retries` (padrão: 2, intervalo estrito $0 \le max\_retries \le 10$), autoriza o ciclo corretivo em `replan`.
- Se o limite for ultrapassado (`validator_attempts > max_retries`), o disjuntor desarma e desvia **obrigatoriamente** para o `supervisor`, que rejeita o plano de forma limpa, auditável e sem exceções não tratadas no motor LangGraph.

### 3.3 Isolamento de Sessão com `MemorySaver`
O grafo suporta persistência em memória via `MemorySaver`, associado à chave `thread_id` nas configurações de invocação (`config={"configurable": {"thread_id": ...}}`). Múltiplas execuções concorrentes mantêm grafos de estado independentes, prevenindo colisões ou vazamentos de estado entre threads paralelas.

### 3.4 Governança Executiva e Server Authority no Supervisor
O nó `supervisor_node` consome as alocações e o relatório de viabilidade através do prompt BART (`configs/prompts/supervisor.yaml`), gerando a saída estruturada `SupervisorOutput(extra="forbid")`. A função de salvaguarda `validate_supervisor_decision` atua como guardião do servidor: se o relatório contiver violações e o supervisor indicar aprovação, lança `ValueError` (em modo estrito) ou aciona o fallback objetivo `deterministic_supervisor_decision`. Quando aprovado, os pontos totais da sprint são recalculados imperativamente no servidor através dos `Task.story_points` canônicos.

---

## 4. Anatomia do Padrão / Fluxo (Design System Spec)

- **Camada de Entrada (DTO / Blackboard):** `SprintState` centralizado contendo `backlog: list[Task]`, `team: list[DeveloperProfile]`, `prioritized_tasks`, `allocations`, `validation_errors`, `sprint_plan` e histórico `messages` com redutor `add_messages`.
- **Camada de Orquestração Cíclica:** Compilação do `StateGraph(SprintState)` ligando nós especializados (`prioritizer`, `allocator`, `validator`, `replan`, `supervisor`).
- **Camada de Roteamento Condicional:** Função determinística `route_after_validation` conectada via `add_conditional_edges("validator", ...)`.
- **Camada de Governança de Servidor (Server Authority):** Esquema Pydantic `SupervisorOutput(extra="forbid")` e salvaguarda `validate_supervisor_decision`.
- **Camada de Saída & Intenção BDI:** Materialização do modelo `SprintPlan` preenchido com dados canônicos em caso de aprovação, ou `sprint_plan = None` com log circunstanciado de rejeição.

---

## 5. Matriz de Estados e Comportamento (State Matrix)

| Estado | Condição de Disparo | Roteamento / Nó Ativo | Código / Status | Resultado no Blackboard |
|---|---|---|---|---|
| **ST-01: Sucesso 1-Pass** | Backlog cabe na capacidade da equipe (ex: Cenário A 10 tarefas / 38 pts <= 100 pts) | `validator` $\to$ `supervisor` $\to$ `END` | `is_approved=True` | `sprint_plan: SprintPlan(...)`, `validation_errors: []`, `status: APPROVED` |
| **ST-02: Auto-correção 2-Pass** | Backlog inicial excede capacidade (ex: Cenário B 128 pts vs 84 pts máx); `attempts <= max_retries` | `validator` $\to$ `replan` $\to$ `allocator` $\to$ `validator` $\to$ `supervisor` | `is_approved=True` (após poda) | Redução para tarefas viáveis ($\le 84$ pts), `sprint_plan` homologado com 0 violações |
| **ST-03: Desarme do Circuit Breaker** | Backlog com restrição insolúvel (ex: skill inexistente na equipe); `attempts > max_retries` | `validator` $\to$ `supervisor` $\to$ `END` | `is_approved=False` | `sprint_plan: None`, `validation_errors: [violações]`, `status: REJECTED` |
| **ST-04: Rejeição Imediata (`max_retries=0`)** | Disjuntor configurado sem retentativas diante de plano inválido | `validator` $\to$ `supervisor` $\to$ `END` | `is_approved=False` | Rejeição sem ciclo corretivo, preservando histórico de violações |
| **ST-05: Tentativa de Fraude / Alucinação** | LLM tenta aprovar plano com violações de FTE ou dependências ativas | `validate_supervisor_decision` intercepta | `Server Authority Enforcement` | Em modo estrito lança `ValueError`; em modo resiliente força `is_approved=False` |
| **ST-06: Isolamento de Sessão Concorrente** | Múltiplas requisições paralelas com `thread_id` distintos via `MemorySaver` | `build_sprint_graph(checkpointer)` | `Session Isolation 200 OK` | Estados completamente estanques, sem cross-talk de variáveis |

---

## 6. Diretrizes de Do's & Don'ts (Boas Práticas vs. Anti-patterns)

| 🟢 DO (Faça) | 🔴 DON'T (Nunca Faça) |
|---|---|
| Use algoritmos determinísticos de seleção (`select_feasible_sprint_tasks`) para poda de escopo baseada em capacidade analítica e DAG. | Nunca permita que o LLM decida livremente quais tarefas descartar sem ancoragem formal nas restrições de FTE e dependências. |
| Delimite o Circuit Breaker em limites seguros ($0 \le max\_retries \le 10$) medidos na janela deliberativa de mensagens. | Nunca construa arestas cíclicas sem contadores ou sem condição terminal garantida, arriscando `GraphRecursionError`. |
| Recalcule `total_points` e a ocupação da equipe a partir dos valores canônicos de `Task.story_points`. | Nunca confie cegamente no somatório de pontos ou nos atributos retornados pela resposta estruturada do LLM. |
| Efetue reset de alocações (`allocations: []`) no nó corretivo para garantir recalibração limpa pelo alocador. | Nunca mantenha alocações parciais de tarefas podadas na tentativa de correção subsequente. |
| Configure `recursion_limit` adequadamente no config de invocação com margem superior a $(max\_retries + 2) \times 5$. | Nunca use limites rígidos inferiores ao número máximo previsto de transições cíclicas entre nós. |

---

## 7. Consequências & Trade-offs

- **Impactos Positivos:**
  - **Superação Completa do n8n:** Substituição definitiva de webhooks lineares frágeis por um grafo de estado cíclico robusto e auditável.
  - **Resolução Autônoma do Cenário B (84 pts):** O nó corretivo poda automaticamente o backlog excedente de 128 pts para o teto viável de 84 pts, homologando a sprint sem intervenção humana em apenas 2 passagens.
  - **Zero Crash por Recursão:** O Circuit Breaker garante que cenários patológicos ou insolúveis terminem com rejeição formal e explicativa, eliminando `GraphRecursionError`.
  - **Isolamento Concorrente Comprovado:** Testado e aprovado com `ThreadPoolExecutor` executando 4 sprints concorrentes simultâneas em 1.11s.
  - **Suíte de Testes Integralmente Verde:** 125 testes automatizados cobrindo 100% dos caminhos críticos de priorização, alocação, validação e governança.
- **Trade-offs / Riscos Assumidos:**
  - **Corte Guloso de Escopo:** Em caso de estouro de capacidade, tarefas de menor prioridade ou sem viabilidade causal na sprint atual são postergadas para sprints subsequentes, exigindo comunicação clara no `sprint_summary`.
  - **Consumo de Mensagens no Blackboard:** Cada ciclo de replanejamento anexa mensagens deliberativas adicionais ao `messages`, gerenciado através do redutor `add_messages`.
