# Camada de Dados — `data/`

> **Diretório responsável pelo armazenamento, procedência, especificação e carregamento de dados dos cenários de teste do Sprint Planning MAS.**

Seguindo as boas práticas de Engenharia de Software e MLOps/LLMOps:
- `data/raw/`: Metadados, procedência acadêmica e especificações brutas (`scenarios_raw_spec.json`).
- `data/processed/`: Arquivos JSON canônicos estruturados e validados contra os modelos Pydantic v2 do `sprint_mas.state` (`Task` e `DeveloperProfile`).
- `evals/golden_dataset/`: Gabarito ótimo de alocação da sprint (`golden_scenario_b.json`) para benchmarking e cálculo de métricas.

---

## 📊 Dicionário de Dados

### 1. Entidade Tarefa (`Task`)
| Campo | Tipo | Restrições | Descrição |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Obrigatório, formato `TSK-XXX` | Identificador único da tarefa no backlog. |
| `title` | `string` | Min 3 caracteres | Título descritivo da história de usuário ou tarefa técnica. |
| `description` | `string` | Texto livre | Detalhamento dos critérios de aceitação e escopo. |
| `story_points` | `integer` | `story_points > 0` | Estimativa de esforço relativo (escala Fibonacci ou linear). |
| `skill_required`| `string` | Ex: `backend`, `frontend`, `fullstack`, `devops`, `mobile`, `data` | Especialidade técnica primária necessária para execução. |
| `priority` | `integer` | `1 <= priority <= 5` | Nível de urgência/valor (1 = máxima prioridade, 5 = menor prioridade). |
| `dependencies` | `list[string]`| Lista de IDs (default: `[]`) | Lista de tarefas que devem ser finalizadas antes de iniciar esta. |

### 2. Entidade Desenvolvedor (`DeveloperProfile`)
| Campo | Tipo | Restrições | Descrição |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Ex: `dev_A`, `dev_B` | Identificador único do desenvolvedor. |
| `name` | `string` | Min 2 caracteres | Nome / papel do membro do time. |
| `skills` | `list[string]`| Lista não-vazia | Habilidades técnicas dominadas pelo profissional. |
| `fte` | `float` | `0.0 <= fte <= 1.0` | Fração de dedicação equivalente a tempo integral (ex: `0.5` = 50% de dedicação). |

---

## 🧪 Procedência dos Cenários (Papers WESAAC 2025 & REIC 2026)

1. **Cenário A (`data/processed/scenario_a.json` — Smoke Test):**
   - 10 tarefas sintéticas (`TSK-001` a `TSK-010`) sem dependências encadeadas complexas.
   - Equipe de 3 desenvolvedores com disponibilidade total (`fte = 1.0`).
   - Propósito: Validação funcional de ponta a ponta do fluxo dos agentes no LangGraph.

2. **Cenário B (`data/processed/scenario_b.json` — Alta Complexidade & Gargalo Real):**
   - Exatamente 30 tarefas (`TSK-101` a `TSK-130`).
   - Exatamente 19 tarefas exigem competência `backend` (63.3% do backlog).
   - Dependências encadeadas presentes (`TSK-102 -> TSK-101`, `TSK-105 -> TSK-104`, `TSK-110 -> TSK-109`, `TSK-115 -> TSK-114`, `TSK-120 -> TSK-119`).
   - Equipe de 5 desenvolvedores com restrições severas do paper:
     - `dev_A`: Frontend Developer (FTE: 1.0)
     - `dev_B`: Backend Specialist (FTE: 0.7)
     - `dev_C`: Fullstack Developer (FTE: 1.0)
     - `dev_D`: Backend Specialist (FTE: 0.5 — gargalo crítico)
     - `dev_E`: Frontend Developer (FTE: 1.0)
   - Propósito: Avaliar se o agente mitiga o gargalo alocando o dev fullstack (`dev_C`) e respeita o teto de 50% do `dev_D`.

3. **Cenário C (`data/processed/scenario_c.json` — Estresse & Escalabilidade):**
   - 100 tarefas sintéticas (`TSK-201` a `TSK-300`) com story points variados e equipe de 10 desenvolvedores.
   - Propósito: Avaliar estabilidade do estado compartilhado, concorrência e ausência de memory leaks sob alta carga.

---

## 🛠️ Como Carregar os Cenários no Código

Utilize o módulo [`sprint_mas.data_loader`](file:///c:/Users/elyss/Desktop/REIC-WESAAC/sprint_mas/data_loader.py):

```python
from sprint_mas import load_scenario, list_available_scenarios

# Listar cenários disponíveis
print(list_available_scenarios())
# Output: ['scenario_a', 'scenario_b', 'scenario_c']

# Carregar cenário com validação automática de DAG e tipagem Pydantic v2
tasks, team = load_scenario("scenario_b")

print(f"Tarefas carregadas: {len(tasks)}")
print(f"Membros da equipe: {len(team)}")
```
