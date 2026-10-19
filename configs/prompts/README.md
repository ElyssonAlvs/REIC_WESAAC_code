# Prompts Versionados como Código — `configs/prompts/`

> **Armazenamento estruturado de System Prompts dos agentes especialistas baseados nas 17 regras da técnica BART.**

---

## 📐 Estrutura Padrão dos Prompts em YAML

Cada arquivo em `configs/prompts/*.yaml` segue o esquema:

```yaml
version: "1.0.0"
agent_name: "PrioritizationAgent"
description: "Agente responsável por ordenar o backlog com base em valor e dependências"
technique: "BART (17 questões de elicitação de requisitos para bots)"
model_parameters:
  temperature: 0.0
  response_format: "json_object"
system_prompt: |
  Você é o Agente de Priorização especialista em Scrum...
  [Regras de negócio, restrições e critérios]
user_template: |
  Backlog a ser analisado:
  {backlog_json}
```

---

## 🎯 Aplicação da Técnica BART (Gerstberger et al., 2024)
Conforme estabelecido no artigo:
- **Gatilho:** Requisição do Product Owner / Scrum Master.
- **Pré-condições:** Backlog estruturado e perfis de equipe carregados.
- **Objetivo:** Retornar o backlog priorizado com dependências mapeadas sem intervenção humana manual.
