"""Módulo para ingestão, validação e carregamento de prompts versionados como código."""

from pathlib import Path
from typing import Any
import yaml
from langchain_core.prompts import ChatPromptTemplate


def get_prompts_dir() -> Path:
    """Localiza dinamicamente o diretório 'configs/prompts' do projeto.

    Returns:
        Path: Caminho absoluto para a pasta de prompts.
    """
    # Localização a partir deste arquivo: REIC-WESAAC/sprint_mas/prompts.py -> REIC-WESAAC/configs/prompts
    prompts_dir = Path(__file__).resolve().parent.parent / "configs" / "prompts"
    if prompts_dir.is_dir():
        return prompts_dir

    cwd_prompts = Path.cwd() / "configs" / "prompts"
    if cwd_prompts.is_dir():
        return cwd_prompts

    return prompts_dir


def load_prompt_yaml(agent_name: str) -> dict[str, Any]:
    """Carrega e valida o arquivo YAML de especificação de prompt de um agente.

    Args:
        agent_name: Nome do agente ou arquivo (ex: 'prioritization', 'allocation', 'supervisor').

    Returns:
        dict[str, Any]: Conteúdo parseado do arquivo YAML contendo metadados e templates.

    Raises:
        FileNotFoundError: Se o arquivo YAML correspondente não existir.
        ValueError: Se chaves essenciais ('system_prompt', 'user_template') estiverem ausentes.
    """
    clean_name = agent_name.strip().lower()
    if clean_name.endswith(".yaml"):
        clean_name = clean_name[:-5]
    elif clean_name.endswith(".yml"):
        clean_name = clean_name[:-4]

    file_path = get_prompts_dir() / f"{clean_name}.yaml"
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Arquivo de prompt não encontrado para o agente '{agent_name}'. "
            f"Arquivo esperado em '{file_path}'."
        )

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Conteúdo inválido no arquivo de prompt '{file_path}'. Esperava-se um dicionário YAML."
        )

    required_keys = {"system_prompt", "user_template"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise ValueError(
            f"Arquivo de prompt '{file_path}' incompleto. Chaves obrigatórias ausentes: {missing_keys}."
        )

    return data


def get_agent_prompt_template(agent_name: str) -> ChatPromptTemplate:
    """Instancia um ChatPromptTemplate do LangChain a partir da especificação YAML do agente.

    Args:
        agent_name: Nome do agente correspondente ao arquivo em configs/prompts/.

    Returns:
        ChatPromptTemplate: Template compilado com mensagens 'system' e 'human'.
    """
    prompt_data = load_prompt_yaml(agent_name)
    system_prompt = prompt_data["system_prompt"]
    user_template = prompt_data["user_template"]

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", user_template),
        ]
    )
