from __future__ import annotations

from app.integrations.openrouter_client import (
    OpenRouterLLMClient,
    build_provider_preferences,
)


class FakeMessage:
    content = "ok"


class FakeChoice:
    message = FakeMessage()


class FakeUsage:
    prompt_tokens = 1
    completion_tokens = 1


class FakeResponse:
    choices = [FakeChoice()]
    model = "fake-model"
    usage = FakeUsage()


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeOpenAI:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


def test_build_provider_preferences() -> None:
    assert build_provider_preferences("", True) is None
    assert build_provider_preferences(" Groq ", False) == {
        "order": ["Groq"],
        "allow_fallbacks": False,
    }
    assert build_provider_preferences("Groq,DeepInfra", True) == {
        "order": ["Groq", "DeepInfra"],
        "allow_fallbacks": True,
    }


def test_openrouter_client_sends_provider_and_reasoning_extra_body() -> None:
    completions = FakeCompletions()
    client = OpenRouterLLMClient(
        api_key="test",
        model="openai/gpt-oss-20b",
        provider={"order": ["Groq"], "allow_fallbacks": False},
        reasoning_effort="low",
    )
    client._client = FakeOpenAI(completions)

    result = client.chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        temperature=0.2,
        max_tokens=10,
    )

    assert result.ok
    assert completions.kwargs["extra_body"] == {
        "provider": {"order": ["Groq"], "allow_fallbacks": False},
        "reasoning": {"effort": "low"},
    }


def test_openrouter_client_omits_extra_body_by_default() -> None:
    completions = FakeCompletions()
    client = OpenRouterLLMClient(api_key="test", model="openai/gpt-4o-mini")
    client._client = FakeOpenAI(completions)

    client.chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        temperature=0.2,
        max_tokens=10,
    )

    assert "extra_body" not in completions.kwargs
