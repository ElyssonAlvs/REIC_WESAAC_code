"""Pytest configuration and global isolation fixtures.

Ensures test executions are 100% offline, isolated from remote tracing,
and protected against leaking real API tokens or triggering remote HTTP calls.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate tests from external API credentials and remote LangSmith telemetry.

    Prevents load_dotenv(override=False) in CLI runners from picking up
    live secrets from a local .env file.
    """
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
