"""Testes unitários para a fábrica de modelos LLM."""

from unittest.mock import MagicMock, patch
import pytest

from sprint_mas.llm_factory import get_llm


def test_get_llm_groq_success(monkeypatch):
    """Garante que o provedor Groq é instanciado com os parâmetros corretos."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-key-12345")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")

    with patch("sprint_mas.llm_factory.ChatGroq") as mock_chat_groq:
        mock_instance = MagicMock()
        mock_chat_groq.return_value = mock_instance

        llm = get_llm(provider="groq", model="custom-groq-model", temperature=0.2)

        mock_chat_groq.assert_called_once_with(
            api_key="gsk-mock-key-12345",
            model="custom-groq-model",
            temperature=0.2,
        )
        assert llm == mock_instance


def test_get_llm_groq_default_model(monkeypatch):
    """Garante que o modelo padrão do Groq é utilizado caso não seja informado."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-key-12345")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")

    with patch("sprint_mas.llm_factory.ChatGroq") as mock_chat_groq:
        mock_instance = MagicMock()
        mock_chat_groq.return_value = mock_instance

        llm = get_llm(provider="groq")

        mock_chat_groq.assert_called_once_with(
            api_key="gsk-mock-key-12345",
            model="llama-3.1-8b-instant",
            temperature=0.0,
        )
        assert llm == mock_instance


def test_get_llm_groq_missing_api_key(monkeypatch):
    """Garante que erro descritivo é lançado se GROQ_API_KEY estiver ausente."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError) as exc_info:
        get_llm(provider="groq")

    assert "GROQ_API_KEY não está configurada" in str(exc_info.value)


def test_get_llm_ollama_success(monkeypatch):
    """Garante que o provedor Ollama é instanciado com parâmetros e base_url corretos."""
    monkeypatch.setenv("OLLAMA_MODEL", "llama3:latest")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    with patch("sprint_mas.llm_factory.ChatOllama") as mock_chat_ollama:
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        llm = get_llm(provider="ollama", model="qwen2.5:7b", temperature=0.5)

        mock_chat_ollama.assert_called_once_with(
            model="qwen2.5:7b",
            base_url="http://localhost:11434",
            temperature=0.5,
        )
        assert llm == mock_instance


def test_get_llm_ollama_defaults(monkeypatch):
    """Garante valores padrão de modelo e base_url para o provedor Ollama."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    with patch("sprint_mas.llm_factory.ChatOllama") as mock_chat_ollama:
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        llm = get_llm(provider="ollama")

        mock_chat_ollama.assert_called_once_with(
            model="llama3:latest",
            base_url="http://localhost:11434",
            temperature=0.0,
        )
        assert llm == mock_instance


def test_get_llm_unsupported_provider():
    """Garante que provedor inválido lança ValueError com mensagem explicativa."""
    with pytest.raises(ValueError) as exc_info:
        get_llm(provider="unsupported_provider_xyz")

    assert "Provedor LLM não suportado" in str(exc_info.value)
    assert "unsupported_provider_xyz" in str(exc_info.value)


def test_get_llm_provider_from_env(monkeypatch):
    """Garante que quando provider=None, o valor é resolvido a partir da env var PROVIDER."""
    monkeypatch.setenv("PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "deepseek-r1:8b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    with patch("sprint_mas.llm_factory.ChatOllama") as mock_chat_ollama:
        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        llm = get_llm()

        mock_chat_ollama.assert_called_once_with(
            model="deepseek-r1:8b",
            base_url="http://127.0.0.1:11434",
            temperature=0.0,
        )
        assert llm == mock_instance
