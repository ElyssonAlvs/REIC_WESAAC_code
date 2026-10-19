"""Fábrica de LLMs desacoplada com suporte a Groq e Ollama."""

import os
from typing import Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

# Carrega variáveis de ambiente do .env se presente
load_dotenv()


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
):
    """Instancia e retorna um cliente LLM baseado no provedor configurado.

    Args:
        provider: 'groq' ou 'ollama'. Se None, lê a variável PROVIDER do ambiente (default: 'groq').
        model: Identificador do modelo. Se None, lê GROQ_MODEL ou OLLAMA_MODEL do ambiente.
        temperature: Temperatura para controle de aleatoriedade da geração (default: 0.0).

    Returns:
        BaseChatModel: Instância configurada de ChatGroq ou ChatOllama.

    Raises:
        ValueError: Se o provedor não for suportado ou se GROQ_API_KEY não estiver configurada para o Groq.
    """
    resolved_provider = (provider or os.getenv("PROVIDER", "groq")).lower().strip()

    if resolved_provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "A variável de ambiente GROQ_API_KEY não está configurada. "
                "Defina GROQ_API_KEY no arquivo .env ou no ambiente antes de utilizar o provedor 'groq'."
            )
        resolved_model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        return ChatGroq(
            api_key=api_key,
            model=resolved_model,
            temperature=temperature,
        )

    if resolved_provider == "ollama":
        resolved_model = model or os.getenv("OLLAMA_MODEL", "llama3:latest")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(
            model=resolved_model,
            base_url=base_url,
            temperature=temperature,
        )

    raise ValueError(
        f"Provedor LLM não suportado: '{resolved_provider}'. "
        "Os provedores suportados são 'groq' e 'ollama'."
    )
