import logging

from aiogram import Router, html, types
from aiogram.filters import Command, CommandObject

from bot import config, message_store, react

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=["blerb"], ignore_mention=True),
)
async def dump_message_info(message: types.Message):
    logger.info(
        "Command /blerb received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    await message.reply(f"chat id: {html.code(message.chat.id)}")


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=["mode_claude"], ignore_mention=True),
)
async def switch_to_claude(message: types.Message):
    logger.info(
        "Command /mode_claude received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_ANTHROPIC)
    logger.info(
        "Provider switched to %s for chat_id=%s",
        config.PROVIDER_ANTHROPIC,
        message.chat.id,
    )
    await message.reply(f"🤖теперь я на мозгах {config.PROVIDER_ANTHROPIC}!")


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=["mode_chatgpt"], ignore_mention=True),
)
async def switch_to_chatgpt(message: types.Message):
    logger.info(
        "Command /mode_chatgpt received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_OPENAI)
    logger.info(
        "Provider switched to %s for chat_id=%s",
        config.PROVIDER_OPENAI,
        message.chat.id,
    )
    await message.reply(f"🤖теперь я на мозгах {config.PROVIDER_OPENAI}!")


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=["mode_yandex"], ignore_mention=True),
)
async def switch_to_yandexgpt(message: types.Message):
    logger.info(
        "Command /mode_yandex received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_YANDEXGPT)
    logger.info(
        "Provider switched to %s for chat_id=%s",
        config.PROVIDER_YANDEXGPT,
        message.chat.id,
    )
    await message.reply(f"🤖теперь я на мозгах {config.PROVIDER_YANDEXGPT}!")


@router.message(config.filter_chat_allowed, Command(commands=["prompt"]))
async def dump_set_prompt(message: types.Message, command: CommandObject):
    logger.info(
        "Command /prompt received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    new_prompt = command.args
    if not new_prompt:
        logger.debug(
            "No new prompt provided, returning current config for chat_id=%s",
            message.chat.id,
        )
        await message.reply(config.rich_info(message.chat.id))
        return

    success = config.override_prompt_for_chat(message.chat.id, new_prompt)
    if success:
        logger.info(
            "Prompt updated for chat_id=%s, new_prompt_length=%d",
            message.chat.id,
            len(new_prompt),
        )
        await message.answer(
            "okie-dokie 👌 prompt изменён но нет никаких гарантий что это надолго"
        )
    else:
        logger.warning("Failed to update prompt for chat_id=%s", message.chat.id)
        await message.answer("nope 🙅")


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=["new_chat"]),
)
async def handle_new_chat(message: types.Message):
    logger.info(
        "Command /new_chat received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    tag = f"matvey-3000:history:{config.me_strip_lower}:{message.chat.id}"
    deleted_count = message_store.clear_conversation_history(tag)
    logger.info(
        "Conversation history cleared for chat_id=%s, deleted_count=%d",
        message.chat.id,
        deleted_count,
    )

    await message.reply(
        f"🔄 Conversation history cleared! ({deleted_count} messages removed)\n"
        f"Starting fresh conversation."
    )
    await react(success=True, message=message)


@router.message(config.filter_is_admin, Command(commands=["admin_stats"]))
async def handle_stats_command(message: types.Message, command: CommandObject):
    logger.info(
        "Command /admin_stats received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    stats = message_store.fetch_stats(keys_pattern="matvey-3000:history:*")
    total_chats = len(config)
    logger.debug("Admin stats: total_keys=%d, total_chats=%d", len(stats), total_chats)
    response = f"Total keys in storage: {len(stats)}"
    per_chat = "\n".join(f"{key}: {count}" for key, count in stats)
    await message.reply(
        "\n".join(["[ADMIN]", response, "===", per_chat, f"Total chats: {total_chats}"])
    )
