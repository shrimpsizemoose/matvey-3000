import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from filters import ConfigFilter


def test_bot_module_import_does_not_construct_dependencies(monkeypatch):
    monkeypatch.delenv('TELEGRAM_API_TOKEN', raising=False)
    monkeypatch.delenv('BOT_CONFIG_TOML', raising=False)
    monkeypatch.delenv('REDIS_URL', raising=False)
    sys.modules.pop('bot', None)

    importlib.import_module('bot')


async def test_config_filter_uses_injected_config():
    method = AsyncMock(return_value=True)
    config = SimpleNamespace(filter_chat_allowed=method)
    message = SimpleNamespace()
    filter_ = ConfigFilter('filter_chat_allowed')

    result = await filter_(message, config=config)

    assert result is True
    method.assert_awaited_once_with(message)


def test_dependency_factory_constructs_external_clients(monkeypatch):
    import bot

    fake_bot = SimpleNamespace()
    fake_config = SimpleNamespace()
    fake_store = SimpleNamespace()
    fake_openai_client = SimpleNamespace()
    fake_anthropic_client = SimpleNamespace()
    monkeypatch.setenv('TELEGRAM_API_TOKEN', '123456:test-token')
    monkeypatch.setenv('BOT_CONFIG_TOML', '/config/test.toml')
    monkeypatch.setenv('REDIS_URL', 'redis://test:6379/0')
    monkeypatch.setattr(bot, 'Bot', Mock(return_value=fake_bot))
    monkeypatch.setattr(bot.Config, 'read_toml', Mock(return_value=fake_config))
    monkeypatch.setattr(bot, 'MessageStore', Mock(return_value=fake_store))
    monkeypatch.setattr(
        bot.openai,
        'AsyncOpenAI',
        Mock(return_value=fake_openai_client),
    )
    monkeypatch.setattr(
        bot.anthropic,
        'AsyncAnthropic',
        Mock(return_value=fake_anthropic_client),
    )

    dependencies = bot.create_dependencies_from_env()

    assert dependencies.bot is fake_bot
    assert dependencies.config is fake_config
    assert dependencies.message_store is fake_store
    assert dependencies.providers.openai_client is fake_openai_client
    assert dependencies.providers.anthropic_client is fake_anthropic_client
