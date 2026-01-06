import logging
import random
import time
import time as time_module

from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject

from bot import bot, config, extract_message_chain, message_store, react
import metrics
from message_store import StoredChatMessage
from providers import TextResponse

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["ru", "en"]),
)
async def translate_ruen(message: types.Message, command: CommandObject):
    logger.info(
        "Command /%s received from chat_id=%s user=%s",
        command.command,
        message.chat.id,
        message.from_user.username,
    )
    if command.command in config[message.chat.id].disabled_commands:
        logger.debug(
            "Command /%s is disabled for chat_id=%s", command.command, message.chat.id
        )
        await react(False, message)
        return
    prompt_tuple = config.fetch_translation_prompt_tuple(command.command)
    messages_to_send = [prompt_tuple, ("user", command.args)]
    logger.debug(
        "Translation request: direction=%s, text_length=%d",
        command.command,
        len(command.args or ""),
    )
    await message.chat.do("typing")
    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=messages_to_send,
    )

    await message.reply(llm_reply.text)
    await react(llm_reply.success, message)


@router.message(F.text, config.filter_chat_allowed)
async def handle_text_message(message: types.Message):
    logger.debug(
        "Text message received from chat_id=%s user=%s, text_length=%d",
        message.chat.id,
        message.from_user.username,
        len(message.text or ""),
    )
    start_time = time_module.perf_counter()
    chat_config = config[message.chat.id]
    save_messages = chat_config.save_messages
    context_enabled = chat_config.context_enabled

    tag = f"matvey-3000:history:{config.me_strip_lower}:{message.chat.id}"

    # if last message is a single word, ignore it
    args = message.text
    args = args.split()
    if len(args) == 1:
        logger.debug("Ignoring single-word message from chat_id=%s", message.chat.id)
        return

    # Determine if we should respond
    should_respond = False

    # Check if this is a reply thread
    message_chain = extract_message_chain(message, bot.id)
    has_bot_in_thread = any(role == "assistant" for role, _ in message_chain)

    if has_bot_in_thread:
        should_respond = True
        logger.debug("Responding to reply thread in chat_id=%s", message.chat.id)
    elif len(message_chain) > 1 and random.random() < 0.95:
        logger.debug("Ignoring thread without bot in chat_id=%s", message.chat.id)
        return
    elif message.chat.id < 0:
        # Group chat - only respond if mentioned
        if any(config.me in x for x in args):
            should_respond = True
            logger.debug("Responding to mention in group chat_id=%s", message.chat.id)
    else:
        # Private chat - always respond
        should_respond = True
        logger.debug("Responding to private chat_id=%s", message.chat.id)

    if not should_respond:
        logger.debug("Not responding to message in chat_id=%s", message.chat.id)
        return

    # Build context for LLM
    system_prompt = config.prompt_tuple_for_chat(message.chat.id)

    if context_enabled and save_messages:
        max_context = chat_config.max_context_messages
        logger.debug(
            "Building context from Redis for chat_id=%s, max_context=%d",
            message.chat.id,
            max_context,
        )
        messages_to_send = message_store.build_context_messages(
            key=tag,
            limit=max_context,
            bot_username=config.me_strip_lower,
            system_prompt=system_prompt,
            max_tokens=4000,
        )
        messages_to_send.append(("user", message.text))
        logger.debug(
            "Context built for chat_id=%s, total_messages=%d",
            message.chat.id,
            len(messages_to_send),
        )
    else:
        logger.debug(
            "Using thread-based context for chat_id=%s, chain_length=%d",
            message.chat.id,
            len(message_chain),
        )
        messages_to_send = [
            system_prompt,
            *message_chain,
        ]

    await message.chat.do("typing")

    provider = config.provider_for_chat_id(message.chat.id)
    model = config.model_for_chat_id(message.chat.id)
    logger.info(
        "Generating LLM response for chat_id=%s, provider=%s, model=%s, context_messages=%d",
        message.chat.id,
        provider,
        model,
        len(messages_to_send),
    )

    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=messages_to_send,
    )

    if llm_reply.success:
        logger.info(
            "LLM response generated successfully for chat_id=%s, response_length=%d",
            message.chat.id,
            len(llm_reply.text),
        )
        metrics.requests_total.labels(command='chat', status='success').inc()
    else:
        logger.warning(
            "LLM response failed for chat_id=%s, error=%s",
            message.chat.id,
            llm_reply.text[:100],
        )
        metrics.requests_total.labels(command='chat', status='error').inc()

    func = message.reply if llm_reply.success else message.answer
    await func(llm_reply.text)

    if save_messages:
        user_msg = StoredChatMessage.from_tg_message(message)
        message_store.save(tag, user_msg)

        bot_msg = StoredChatMessage(
            chat_name=message.chat.full_name,
            from_username=config.me_strip_lower,
            from_full_name="BOT",
            text=llm_reply.text,
            timestamp=int(time.time()),
        )
        message_store.save(tag, bot_msg)
        logger.debug(
            "Saved user and bot messages to Redis for chat_id=%s", message.chat.id
        )

    metrics.request_duration.labels(command='chat').observe(time_module.perf_counter() - start_time)
    await react(llm_reply.success, message)
