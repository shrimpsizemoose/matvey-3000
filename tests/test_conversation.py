import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# The application currently uses a flat, non-packaged src directory.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from conversation import (
    ChatMessage,
    ConversationProviderRegistry,
    ConversationResult,
    OpenAIConversationProvider,
)
from providers import TextResponse


@pytest.fixture
def openai_client():
    client = SimpleNamespace()
    client.chat = SimpleNamespace()
    client.chat.completions = SimpleNamespace(create=AsyncMock())
    return client


async def test_openai_provider_forwards_model_and_messages(openai_client):
    openai_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Hello from OpenAI"),
            )
        ]
    )
    provider = OpenAIConversationProvider(openai_client)

    result = await provider.generate(
        model="test-model",
        messages=[
            ChatMessage(role="system", content="Be helpful"),
            ChatMessage(role="user", content="Hello"),
        ],
    )

    assert result.success is True
    assert result.text == "Hello from OpenAI"
    openai_client.chat.completions.create.assert_awaited_once_with(
        model="test-model",
        messages=[
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ],
    )


async def test_openai_provider_returns_failure_on_timeout(openai_client):
    openai_client.chat.completions.create.side_effect = TimeoutError("too slow")
    provider = OpenAIConversationProvider(openai_client)

    result = await provider.generate(
        model="test-model",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    assert result.success is False
    assert "too slow" in result.text


def test_provider_registry_returns_registered_provider(openai_client):
    registry = ConversationProviderRegistry()
    provider = OpenAIConversationProvider(openai_client)

    registry.register("openai", provider)

    assert registry.get("openai") is provider


def test_provider_registry_rejects_duplicate_names(openai_client):
    registry = ConversationProviderRegistry()
    provider = OpenAIConversationProvider(openai_client)
    registry.register("openai", provider)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("openai", provider)


def test_provider_registry_rejects_unknown_provider():
    registry = ConversationProviderRegistry()

    with pytest.raises(ValueError, match="Unsupported conversation provider"):
        registry.get("ollama")


async def test_text_response_routes_openai_through_registry():
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ConversationResult(success=True, text="adapter response")
        )
    )
    registry = ConversationProviderRegistry()
    registry.register("openai", provider)
    providers = SimpleNamespace(conversation_providers=registry)
    config = SimpleNamespace(
        PROVIDER_OPENAI="openai",
        PROVIDER_ANTHROPIC="anthropic",
        PROVIDER_YANDEXGPT="yandexgpt",
        provider_for_chat_id=lambda _chat_id: "openai",
        model_for_chat_id=lambda _chat_id: "test-model",
    )

    result = await TextResponse.generate(
        providers=providers,
        config=config,
        chat_id=123,
        messages=[("user", "Hello")],
    )

    assert result == TextResponse(success=True, text="adapter response")
    provider.generate.assert_awaited_once_with(
        model="test-model",
        messages=[ChatMessage(role="user", content="Hello")],
    )
