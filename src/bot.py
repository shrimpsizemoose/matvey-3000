from __future__ import annotations

import asyncio
import collections
import logging
import os
import random

from aiogram import Bot, Dispatcher, F, Router, html, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage

from config import Config
import metrics
from message_store import MessageStore

API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot_props = DefaultBotProperties(parse_mode="HTML")
bot = Bot(token=API_TOKEN, default=bot_props)
message_store = MessageStore.from_env()
config = Config.read_toml(path=os.getenv("BOT_CONFIG_TOML"))


def extract_message_chain(last_message_in_thread: types.Message, bot_id: int):
    payload = collections.deque()
    cur = last_message_in_thread
    while cur is not None:
        try:
            tmp = cur.reply_to_message
            if tmp is not None:
                role = "assistant" if tmp.from_user.id == bot_id else "user"
                if tmp.text:
                    payload.appendleft((role, tmp.text))
                elif tmp.caption:
                    payload.appendleft(
                        (role, f"imagine an image with comment: {tmp.caption}")
                    )
                cur = tmp
            else:
                break
        except AttributeError:
            break
    payload.append(("user", last_message_in_thread.text))
    return [(role, text) for role, text in payload]


async def react(success: bool, message: types.Message):
    yes = config.positive_emojis
    nope = config.negative_emojis
    emoji = random.choice(yes) if success else random.choice(nope)
    reaction = types.reaction_type_emoji.ReactionTypeEmoji(type="emoji", emoji=emoji)
    await message.react(reaction=[reaction])


async def get_replied_photo_bytes(message: types.Message) -> bytes | None:
    """Extract photo bytes from replied-to message."""
    reply = message.reply_to_message
    if not reply or not reply.photo:
        return None
    photo = reply.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    return file_bytes.read()


async def main() -> None:
    logger.info(
        "Starting bot with config version=%s, bot_username=%s",
        config.version,
        config.me,
    )
    logger.info("Configured chats: %d, git_sha=%s", len(config), config.git_sha)

    metrics.start_metrics_server()
    logger.info("Metrics server started on port %d", metrics.METRICS_PORT)

    redis_url = os.getenv("REDIS_URL")
    fsm_prefix = os.getenv("FSM_REDIS_PREFIX", f"fsm:{config.me_strip_lower}")
    storage = RedisStorage.from_url(
        redis_url,
        key_builder=DefaultKeyBuilder(prefix=fsm_prefix),
        state_ttl=300,
        data_ttl=300,
    )
    logger.info("FSM storage initialized with prefix=%s", fsm_prefix)

    # Import handlers and include routers
    from handlers import include_all_routers

    dp = Dispatcher(storage=storage)
    include_all_routers(dp)

    logger.info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
