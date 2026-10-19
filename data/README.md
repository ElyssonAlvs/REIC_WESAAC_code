# Camada de Dados — `data/`

> **Diretório responsável pelo armazenamento, procedência e dicionário de dados dos cenários de teste do Sprint Planning MAS.**

Seguindo as boas práticas de MLOps/LLMOps:
- `data/raw/`: Dados brutos originais e transcrições preliminares (dados imutáveis de entrada).
- `data/processed/`: Arquivos JSON estruturados e validados contra os esquemas Pydantic v2 do `sprint_mas.state` (`Task` e `DeveloperProfile`).

---

## 📊 Dicionário de Dados

### 1. Entidade Tarefa (`Task`)
| Campo | Tipo | Restrições | Descrição |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Obrigatório, formato `TSK-XXX` | Identificador único da tarefa no backlog. |
| `title` | `string` | Min 3 caracteres | Título descritivo da história de usuário ou tarefa técnica. |
| `description` | `string` | Texto livre | Detalhamento dos critérios de aceitação e escopo. |
| `story_points` | `integer` | `story_points > 0` | Estimativa de esforço relativo (escala Fibonacci ou linear). |
| `skill_required`| `string` | Ex: `backend`, `frontend`, `fullstack`, `devops` | Especialidade técnica necessária para execução. |
| `priority` | `integer` | `1 <= priority <= 5` | Nível de urgência/valor (1 = máxima prioridade, 5 = menor prioridade). |
| `dependencies` | `list[string]`| Lista de IDs (default: `[]`) | Lista de tarefas que devem ser finalizadas antes de iniciar esta. |

### 2. Entidade Desenvolvedor (`DeveloperProfile`)
| Campo | Tipo | Restrições | Descrição |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Ex: `dev_A`, `dev_B` | Identificador único do desenvolvedor. |
| `name` | `string` | Min 2 caracteres | Nome do membro do time. |
| `skills` | `list[string]`| Lista não-vazia | Habilidades técnicas dominadas pelo profissional. |
| `fte` | `float` | `0.0 <= fte <= 1.0` | Fração de dedicação equivalente a tempo integral (ex: `0.5` = 50% de dedicação). |

---

## 🧪 Procedência dos Cenários (Artigo REIC 2026)

1. **Cenário A (`scenario_a.json` — Smoke Test):**
   - 10 tarefas simples sem dependências críticas.
   - Equipe com disponibilidade total (`fte = 1.0`).
   - Propósito: Validação funcional de ponta a ponta do fluxo dos agentes.
2. **Cenário B (`scenario_b.json` — Alta Complexidade):**
   - 30 tarefas (`TSK-101` a `TSK-130`) com dependências encadeadas em cadeia.
   - Equipe de 5 desenvolvedores com restrições severas:
     - `dev_B` (Backend): 0.7 FTE.
     - `dev_D` (Backend): 0.5 FTE (gargalo crítico: 63% do backlog é backend).
     - `dev_C` (Fullstack): 1.0 FTE.
   - Propósito: Avaliar se o agente mitiga o gargalo alocando o dev fullstack e respeita o teto de 50% do `dev_D`.
3. **Cenário C (`scenario_c.json` — Estresse e Escalabilidade):**
   - Conjunto massivo de triggers e requisições para teste de concorrência e buffer de memória.
