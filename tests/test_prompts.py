"""Bateria de testes unitários para carregamento de prompts YAML e templates LangChain."""

import pytest
from langchain_core.prompts import ChatPromptTemplate

from sprint_mas.prompts import get_agent_prompt_template, load_prompt_yaml


@pytest.mark.parametrize("agent_name", ["prioritization", "allocation", "supervisor"])
def test_load_prompt_yaml_success(agent_name):
    """Valida o carregamento dos 3 arquivos de prompt YAML e a integridade de seus metadados."""
    data = load_prompt_yaml(agent_name)

    assert isinstance(data, dict)
    assert data["version"] == "1.0.0"
    assert "agent_name" in data
    assert "system_prompt" in data
    assert "user_template" in data
    assert "model_parameters" in data
    assert data["model_parameters"]["response_format"] == "json_object"

    # Valida presença explícita da técnica BART e engenharia de prompt requerida pelo Tech Lead
    assert "BART" in data["elicitation_methodology"]
    assert "technique" in data
    assert "bart_specification" in data
    assert "prompt_engineering_techniques" in data

    bart = data["bart_specification"]
    for key in ["persona", "trigger", "preconditions", "actions", "constraints", "postconditions"]:
        assert key in bart


def test_load_prompt_yaml_not_found():
    """Garante que FileNotFoundError é lançado para agentes sem arquivo de prompt correspondente."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_prompt_yaml("agente_inexistente_xyz")
    assert "Arquivo de prompt não encontrado" in str(exc_info.value)


@pytest.mark.parametrize("agent_name", ["prioritization", "allocation", "supervisor"])
def test_get_agent_prompt_template_compilation(agent_name):
    """Valida a compilação do ChatPromptTemplate com papéis de sistema e usuário."""
    prompt_template = get_agent_prompt_template(agent_name)

    assert isinstance(prompt_template, ChatPromptTemplate)
    messages = prompt_template.messages
    assert len(messages) == 2
    assert messages[0].prompt.template  # System message
    assert messages[1].prompt.template  # Human message


def test_prompt_template_placeholders():
    """Valida que os templates contêm exatamente os placeholders requeridos pelos nós do grafo."""
    prio_tpl = get_agent_prompt_template("prioritization")
    assert set(prio_tpl.input_variables) == {"backlog_json", "topological_order_json"}

    alloc_tpl = get_agent_prompt_template("allocation")
    assert set(alloc_tpl.input_variables) == {"prioritized_tasks_json", "team_json", "capacity_json"}

    sup_tpl = get_agent_prompt_template("supervisor")
    assert set(sup_tpl.input_variables) == {"allocations_json", "feasibility_json", "sprint_goal"}

