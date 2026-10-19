# ADR 0002: Padrão Arquitetural Blackboard com Pydantic v2 e TypedDict

- **Status:** Aceito
- **Data:** 2026-10-02
- **Decisores:** Elysson Alves de Lacerda (Tech Lead), Antigravity (Tech Manager)
- **Contexto Técnico:** Definição da representação de estado compartilhado entre os agentes de IA.

---

## Contexto e Forças Impulsionadoras

Em Sistemas Multiagentes (SMA), a coordenação de múltiplos especialistas cognitivos (Priorização, Alocação, Validação) sobre um problema comum (Sprint Planning) exige um mecanismo de comunicação eficiente.

Duas abordagens eram possíveis:
1. **Passagem de Mensagens Ponto a Ponta (Message Passing):** O Agente A chama o Agente B diretamente passando seus dados.
2. **Quadro-Negro Centralizado (Blackboard Pattern):** Todos os agentes leem de uma memória de trabalho compartilhada e escrevem seus incrementos de solução nesse mesmo repositório.

A passagem ponto a ponto provou ser frágil no n8n (acoplamento temporal, perda de visão global do backlog). Além disso, dados gerados por LLMs podem conter alucinações de valores limites (ex: Story Points negativos, alocações de FTE acima de 1.0).

---

## Decisão

Adotamos o padrão clássico de **Blackboard** materializado pelo `SprintState` (`TypedDict`) e validado por esquemas estritos do **Pydantic v2**:

1. **Memória de Trabalho Única:** O `SprintState` centraliza `backlog`, `team`, `prioritized_tasks`, `allocations`, `validation_errors`, `sprint_plan` e `messages`.
2. **Validações de Borda (Type Safety):**
   - `Task`: `story_points > 0`, `1 <= priority <= 5`.
   - `DeveloperProfile`: `0.0 <= fte <= 1.0` (proíbe sobrecarga além de 100%).
3. **Preservação Histórica:** Uso do redutor `add_messages` do LangGraph para evitar que novas mensagens de deliberação apaguem o histórico anterior.

---

## Consequências

### Positivas
- **Isolamento de Responsabilidades:** Cada agente só toca nos campos de sua competência.
- **Fail-Fast:** Erros de tipo ou limites numéricos são barrados na raiz pelo Pydantic antes de propagarem no grafo.
- **Auditabilidade:** É possível inspecionar o estado exato da sprint em qualquer ponto intermediário da execução.

### Negativas / Mitigações
- Exige conversão explícita entre dicionários de estado e modelos Pydantic ao manipular nós do grafo.
