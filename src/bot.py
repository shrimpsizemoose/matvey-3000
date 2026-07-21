from __future__ import annotations

import asyncio
import collections
import logging
import os
import random
from dataclasses import dataclass

import openai
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage

import metrics
from config import Config
from conversation import ConversationProviderRegistry, OpenAIConversationProvider
from message_store import MessageStore
from providers import ProviderDependencies, ProviderSettings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApplicationDependencies:
    bot: Bot
    config: Config
    message_store: MessageStore
    providers: ProviderDependencies


def extract_message_chain(last_message_in_thread: types.Message, bot_id: int):
    payload = collections.deque()
    cur = last_message_in_thread
    while cur is not None:
        try:
            tmp = cur.reply_to_message
            if tmp is not None:
                role = 'assistant' if tmp.from_user.id == bot_id else 'user'
                if tmp.text:
                    payload.appendleft((role, tmp.text))
                elif tmp.caption:
                    payload.appendleft(
                        (role, f'imagine an image with comment: {tmp.caption}')
                    )
                cur = tmp
            else:
                break
        except AttributeError:
            break
    payload.append(('user', last_message_in_thread.text))
    return [(role, text) for role, text in payload]


async def react(success: bool, message: types.Message, config: Config):
    emojis = config.positive_emojis if success else config.negative_emojis
    reaction = types.reaction_type_emoji.ReactionTypeEmoji(
        type='emoji',
        emoji=random.choice(emojis),
    )
    await message.react(reaction=[reaction])


async def get_replied_photo_bytes(message: types.Message, bot: Bot) -> bytes | None:
    """Extract photo bytes from replied-to message."""
    reply = message.reply_to_message
    if not reply or not reply.photo:
        return None
    photo = reply.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    return file_bytes.read()


def create_dependencies_from_env() -> ApplicationDependencies:
    bot = Bot(
        token=os.environ['TELEGRAM_API_TOKEN'],
        default=DefaultBotProperties(parse_mode='HTML'),
    )
    config = Config.read_toml(path=os.environ['BOT_CONFIG_TOML'])
    message_store = MessageStore(os.environ['REDIS_URL'])
    openai_client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    conversation_providers = ConversationProviderRegistry()
    conversation_providers.register(
        'openai',
        OpenAIConversationProvider(openai_client),
    )
    providers = ProviderDependencies(
        conversation_providers=conversation_providers,
        openai_client=openai_client,
        settings=ProviderSettings(
            kandinski_api_key=os.getenv('KANDINSKI_API_KEY', 'KandiKeyOopsie'),
            kandinski_api_secret=os.getenv('KANDINSKI_API_SECRET', 'KandiSecretOopsie'),
        ),
    )
    return ApplicationDependencies(
        bot=bot,
        config=config,
        message_store=message_store,
        providers=providers,
    )


async def main() -> None:
    dependencies = create_dependencies_from_env()
    bot = dependencies.bot
    config = dependencies.config
    message_store = dependencies.message_store
    providers = dependencies.providers
    logger.info(
        'Starting bot with config version=%s, bot_username=%s',
        config.version,
        config.me,
    )
    logger.info('Configured chats: %d, git_sha=%s', len(config), config.git_sha)

    metrics.start_metrics_server()
    logger.info('Metrics server started on port %d', metrics.METRICS_PORT)

    redis_url = os.environ['REDIS_URL']
    fsm_prefix = os.getenv('FSM_REDIS_PREFIX', f'fsm:{config.me_strip_lower}')
    storage = RedisStorage.from_url(
        redis_url,
        key_builder=DefaultKeyBuilder(prefix=fsm_prefix),
        state_ttl=300,
        data_ttl=300,
    )
    logger.info('FSM storage initialized with prefix=%s', fsm_prefix)

    from handlers import include_all_routers

    dp = Dispatcher(storage=storage)
    dp['config'] = config
    dp['message_store'] = message_store
    dp['providers'] = providers
    include_all_routers(dp)

    logger.info('Bot polling started')
    try:
        await dp.start_polling(bot)
    finally:
        await providers.openai_client.close()


if __name__ == '__main__':
    asyncio.run(main())
