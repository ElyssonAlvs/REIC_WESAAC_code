# Camada de Configurações e Prompts — `configs/`

> **Diretório responsável por armazenar parâmetros de modelos, hiperparâmetros de execução e system prompts versionados como código.**

No padrão LLMOps, **prompts são tratados como código de produção**. Qualquer alteração de pontuação, exemplo ou restrição no texto do prompt pode alterar o comportamento deliberativo do agente, a taxa de sucesso ou os custos de inferência.

---

## 📁 Estrutura do Diretório

```
configs/
├── README.md               # Este documento
├── models.yaml             # Configurações de modelos, temperatura, timeouts e limites
└── prompts/                # Prompts estruturados por agente
    ├── README.md           # Regras de engenharia de prompt e técnica BART
    ├── supervisor.yaml     # Prompt do Agente Supervisor / Orquestrador
    ├── prioritization.yaml # Prompt do Agente de Priorização
    └── allocation.yaml     # Prompt do Agente de Alocação de Recursos
```

---

## 🔒 Princípios de Versionamento de Prompts

1. **Imutabilidade e Semântica:** Ao refinar um prompt, mantenha o histórico versionado no Git.
2. **Separação Código / Instrução:** Nenhum prompt longo deve ficar hardcoded no meio das funções Python; o código deve ler arquivos estruturados de `configs/prompts/`.
3. **Template com Variáveis Tipadas:** Os prompts utilizam placeholders explícitos (ex: `{backlog_json}`, `{team_json}`) preenchidos dinamicamente pelo LangChain `ChatPromptTemplate`.
