# ADR 0004: Padronização de Cenários de Teste, Data Loader e Validação de DAG

## Status
**Aceito** (2026-10-19)

## Contexto
O sistema Sprint Planning Multi-Agent System (sprint-mas) requer uma suíte determinística e reprodutível de dados de entrada para benchmarking e validação das decisões dos agentes cognitivos (PO, Scrum Master, Allocator e Validator).
Nos artigos originais (WESAAC 2025 e REIC 2026), os testes foram descritos conceitualmente com um gargalo severo de competência técnica em backend (63.3% do backlog) e restrição de disponibilidade (dev_D com 0.5 FTE).
Para garantir paridade científica, reprodutibilidade contínua e desacoplamento do motor de orquestração (LangGraph), é imperativo estabelecer:
1. Esquema de dados formal e imutável para os cenários canônicos (A, B e C).
2. Camada utilitária de carregamento com conversão direta para os modelos Pydantic v2 do domínio (`Task` e `DeveloperProfile`).
3. Validação matemática rigorosa do grafo direcionado acíclico (DAG) de dependências entre tarefas, impedindo ciclos, dependências órfãs e auto-dependências antes que o estado seja injetado no LangGraph.

## Decisão de Arquitetura

1. **Separação Estrutural de Dados (`data/`)**:
   - `data/raw/scenarios_raw_spec.json`: Metadados, procedência acadêmica e parâmetros brutos dos cenários.
   - `data/processed/`: Arquivos canônicos (`scenario_a.json`, `scenario_b.json`, `scenario_c.json`) contendo tarefas e perfis de desenvolvedores estruturados.
   - `evals/golden_dataset/golden_scenario_b.json`: Gabarito ótimo de alocação para avaliação automática de métricas (Precision, Recall, Resource Utilization).

2. **Módulo `sprint_mas.data_loader`**:
   - Fornece resolução dinâmica e resiliente do caminho de dados (`get_data_dir`).
   - Fornece listagem determinística de cenários disponíveis (`list_available_scenarios`).
   - Implementa a função de validação topológica `validate_dependencies_dag(tasks)` baseada em DFS com coloração de 3 estados (WHITE, GRAY, BLACK), garantindo complexidade $O(V + E)$ e prevenção de deadlocks no grafo do LangGraph.
   - Fornece `load_scenario(scenario_name)` com validação estrita de integridade Pydantic, verificação de unicidade de chaves primárias e conformidade do DAG.

3. **Cenário B como Benchmark Central de Decisão**:
   - Exatamente 30 tarefas (`TSK-101` a `TSK-130`), sendo 19 de backend.
   - 5 desenvolvedores com perfis e restrições de FTE estritos do paper (`dev_A` 1.0, `dev_B` 0.7, `dev_C` 1.0 Fullstack, `dev_D` 0.5 Backend, `dev_E` 1.0).
   - O sucesso da mitigação do gargalo consiste na realocação ótima de `dev_C` para suprir a sobrecarga de backend respeitando o teto de 0.5 FTE de `dev_D`.

## Consequências

### Positivas:
- **Reprodutibilidade Científica**: Qualquer execução dos agentes pode ser comparada diretamente contra o `golden_scenario_b.json`.
- **Prevenção Antecipada de Falhas**: Ciclos ou referências corrompidas de tarefas são interceptados no momento do carregamento, impedindo loops infinitos no runtime do LangGraph.
- **Tipagem Forte**: Dados brutos JSON são convertidos imediatamente para objetos tipados Pydantic (`Task` e `DeveloperProfile`).

### Neutras/Trade-offs:
- A adição de novos cenários exige conformidade estrita com o esquema JSON e inexistência de dependências cíclicas.
