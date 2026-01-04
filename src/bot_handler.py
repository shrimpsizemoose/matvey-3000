from __future__ import annotations

import asyncio
import base64
import collections
import io
import logging
import os
import random
import time

import openai
import tiktoken
from PIL import Image

from aiogram import F
from aiogram import Bot, Dispatcher, Router, html, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

from config import Config
from chat_completions import TextResponse, ImageResponse
from message_store import MessageStore, StoredChatMessage


API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot_props = DefaultBotProperties(parse_mode='HTML')
bot = Bot(token=API_TOKEN, default=bot_props)
router = Router()
message_store = MessageStore.from_env()

config = Config.read_toml(path=os.getenv('BOT_CONFIG_TOML'))


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
                        (role, f'представь картинку с комментарием {tmp.caption}')
                    )
                cur = tmp
            else:
                break
        except AttributeError:
            break
    payload.append(('user', last_message_in_thread.text))
    return [(role, text) for role, text in payload]


async def react(success, message):
    yes = config.positive_emojis
    nope = config.negative_emojis
    react = random.choice(yes) if success else random.choice(nope)
    react = types.reaction_type_emoji.ReactionTypeEmoji(type='emoji', emoji=react)
    await message.react(reaction=[react])


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['blerb'], ignore_mention=True),
)
async def dump_message_info(message: types.Message):
    logger.info('Command /blerb received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    await message.reply(f'chat id: {html.code(message.chat.id)}')


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['mode_claude'], ignore_mention=True),
)
async def switch_to_claude(message: types.Message):
    logger.info('Command /mode_claude received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_ANTHROPIC)
    logger.info('Provider switched to %s for chat_id=%s', config.PROVIDER_ANTHROPIC, message.chat.id)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_ANTHROPIC}!')


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['mode_chatgpt'], ignore_mention=True),
)
async def switch_to_chatgpt(message: types.Message):
    logger.info('Command /mode_chatgpt received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_OPENAI)
    logger.info('Provider switched to %s for chat_id=%s', config.PROVIDER_OPENAI, message.chat.id)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_OPENAI}!')


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['mode_yandex'], ignore_mention=True),
)
async def switch_to_yandexgpt(message: types.Message):
    logger.info('Command /mode_yandex received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_YANDEXGPT)
    logger.info('Provider switched to %s for chat_id=%s', config.PROVIDER_YANDEXGPT, message.chat.id)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_YANDEXGPT}!')


@router.message(config.filter_chat_allowed, Command(commands=['prompt']))
async def dump_set_prompt(message: types.Message, command: types.CommandObject):
    logger.info('Command /prompt received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    new_prompt = command.args
    if not new_prompt:
        logger.debug('No new prompt provided, returning current config for chat_id=%s', message.chat.id)
        await message.reply(config.rich_info(message.chat.id))
        return

    success = config.override_prompt_for_chat(message.chat.id, new_prompt)
    if success:
        logger.info('Prompt updated for chat_id=%s, new_prompt_length=%d', message.chat.id, len(new_prompt))
        await message.answer(
            'okie-dokie 👌 prompt изменён но нет никаких гарантий что это надолго'
        )
    else:
        logger.warning('Failed to update prompt for chat_id=%s', message.chat.id)
        await message.answer('nope 🙅')


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=['new_chat']),
)
async def handle_new_chat(message: types.Message):
    """Clear conversation history and start fresh."""
    logger.info('Command /new_chat received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
    deleted_count = message_store.clear_conversation_history(tag)
    logger.info('Conversation history cleared for chat_id=%s, deleted_count=%d', message.chat.id, deleted_count)

    await message.reply(
        f'🔄 Conversation history cleared! ({deleted_count} messages removed)\n'
        f'Starting fresh conversation.'
    )
    await react(success=True, message=message)


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=['pic']),
)
async def gimme_pic(message: types.Message, command: types.CommandObject):
    logger.info('Command /pic received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    prompt = command.args
    logger.debug('DALL-E image generation requested, prompt=%r', prompt)
    await message.chat.do('upload_photo')
    try:
        response = await ImageResponse.generate(prompt, mode='dall-e')
    except openai.BadRequestError as e:
        logger.warning('DALL-E generation failed for chat_id=%s, prompt=%r, error=%s', message.chat.id, prompt, e)
        messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
        messages_to_send.append(
            (
                'user',
                f'объясни трагикомичной шуткой почему OpenAI не может сгенерировать картинку по запросу "{prompt}"',  # noqa
            )
        )
        await message.chat.do('typing')
        llm_reply = await TextResponse.generate(
            config=config,
            chat_id=message.chat.id,
            messages=messages_to_send,
        )
        await message.answer(llm_reply.text)
        await react(success=False, message=message)
    else:
        logger.info('DALL-E image generated successfully for chat_id=%s', message.chat.id)
        await message.chat.do('upload_photo')
        image_from_url = types.URLInputFile(response.b64_or_url)
        caption = f'DALL-E 2 prompt: {prompt}'
        await message.answer_photo(image_from_url, caption=caption)
        await react(success=True, message=message)


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=['pic3']),
)
async def gimme_pic3(message: types.Message, command: types.CommandObject):
    logger.info('Command /pic3 received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    prompt = command.args
    logger.debug('DALL-E 3 image generation requested, prompt=%r', prompt)
    await message.chat.do('upload_photo')
    try:
        response = await ImageResponse.generate(prompt, mode='dall-e-3')
    except openai.BadRequestError as e:
        logger.warning('DALL-E 3 generation failed for chat_id=%s, prompt=%r, error=%s', message.chat.id, prompt, e)
        messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
        messages_to_send.append(
            (
                'user',
                f'объясни трагикомичной шуткой почему OpenAI не может сгенерировать картинку по запросу "{prompt}"',  # noqa
            )
        )
        await message.chat.do('typing')
        llm_reply = await TextResponse.generate(
            config=config,
            chat_id=message.chat.id,
            messages=messages_to_send,
        )
        await message.answer(llm_reply.text)
        await react(success=False, message=message)
    else:
        logger.info('DALL-E 3 image generated successfully for chat_id=%s', message.chat.id)
        await message.chat.do('upload_photo')
        image_from_url = types.URLInputFile(response.b64_or_url)
        caption = f'DALL-E 3 prompt: {prompt}'
        await message.answer_photo(image_from_url, caption=caption)
        await react(success=True, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=['pik']),
)
async def gimme_pikk(message: types.Message, command: types.CommandObject):
    logger.info('Command /pik received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    if command.command in config[message.chat.id].disabled_commands:
        logger.debug('Command /pik is disabled for chat_id=%s', message.chat.id)
        react(False, message)
        return
    prompt = command.args
    logger.debug('Kandinski image generation requested, prompt=%r', prompt)
    await message.chat.do('upload_photo')
    try:
        response = await ImageResponse.generate(prompt, mode='kandinski')
    except openai.BadRequestError as e:
        logger.warning('Kandinski generation failed for chat_id=%s, prompt=%r, error=%s', message.chat.id, prompt, e)
        messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
        messages_to_send.append(
            (
                'user',
                f'объясни шуткой почему нельзя сгенерировать картинку по запросу "{prompt}"',  # noqa
            )
        )
        await message.chat.do('typing')
        llm_reply = await TextResponse.generate(
            config=config,
            chat_id=message.chat.id,
            messages=messages_to_send,
        )
        await message.answer(llm_reply.text)
        await react(success=False, message=message)
    else:
        await message.chat.do('upload_photo')
        if response.censored:
            logger.warning('Kandinski response censored for chat_id=%s, prompt=%r', message.chat.id, prompt)
            messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
            messages_to_send.append(
                (
                    'user',
                    f'объясни шуткой почему нельзя сгенерировать картинку по запросу "{prompt}"',  # noqa
                )
            )
            await message.chat.do('typing')
            llm_reply = await TextResponse.generate(
                config=config,
                chat_id=message.chat.id,
                messages=messages_to_send,
            )
            await message.answer(llm_reply.text)
            await react(success=False, message=message)
        else:
            logger.info('Kandinski image generated successfully for chat_id=%s', message.chat.id)
            caption = f'Kandinksi-3 prompt: {prompt}'

            im_b64 = response.b64_or_url.encode()
            im_f = base64.decodebytes(im_b64)
            image = types.BufferedInputFile(
                im_f,
                'kandinski.png',
            )

            await message.answer_photo(
                photo=image,
                caption=caption,
            )
            await react(success=True, message=message)


@router.message(
    F.photo,
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=['edit_pic'], ignore_mention=True),
)
async def handle_edit_pic(message: types.Message, command: types.CommandObject):
    logger.info('Command /edit_pic received from chat_id=%s user=%s',
                message.chat.id, message.from_user.username)

    prompt = command.args
    if not prompt:
        logger.debug('No prompt provided for /edit_pic in chat_id=%s', message.chat.id)
        await message.reply(
            'Пожалуйста, добавь описание того, как отредактировать картинку.\n'
            'Пример: <code>/edit_pic сделай фон зелёным</code>'
        )
        await react(success=False, message=message)
        return

    await message.chat.do('upload_photo')

    try:
        photo = message.photo[-1]
        logger.debug('Downloading photo: file_id=%s, width=%d, height=%d',
                     photo.file_id, photo.width, photo.height)

        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)

        # Convert to 512x512 PNG (DALL-E 2 requirement)
        image = Image.open(file_bytes)
        image = image.convert('RGBA')
        image = image.resize((512, 512), Image.Resampling.LANCZOS)

        png_buffer = io.BytesIO()
        image.save(png_buffer, format='PNG')
        png_bytes = png_buffer.getvalue()
        logger.debug('Image converted to PNG: size=%d bytes', len(png_bytes))

        response = await ImageResponse.edit(png_bytes, prompt)

        if response.success:
            logger.info('Image edit successful for chat_id=%s', message.chat.id)
            image_from_url = types.URLInputFile(response.b64_or_url)
            caption = f'DALL-E 2 edit: {prompt}'
            await message.answer_photo(image_from_url, caption=caption)
            await react(success=True, message=message)
        else:
            logger.warning('Image edit failed for chat_id=%s: %s',
                           message.chat.id, response.b64_or_url[:100])
            await message.reply(response.b64_or_url)
            await react(success=False, message=message)

    except Exception as e:
        logger.error('Error processing /edit_pic for chat_id=%s: %s',
                     message.chat.id, e, exc_info=True)
        await message.reply(f'Ошибка при редактировании картинки: {e}')
        await react(success=False, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=['ru', 'en']),
)
async def translate_ruen(message: types.Message, command: types.CommandObject):
    logger.info('Command /%s received from chat_id=%s user=%s', command.command, message.chat.id, message.from_user.username)
    if command.command in config[message.chat.id].disabled_commands:
        logger.debug('Command /%s is disabled for chat_id=%s', command.command, message.chat.id)
        react(False, message)
        return
    prompt_tuple = config.fetch_translation_prompt_tuple(command.command)
    messages_to_send = [prompt_tuple, ('user', command.args)]
    logger.debug('Translation request: direction=%s, text_length=%d', command.command, len(command.args or ''))
    await message.chat.do('typing')
    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=messages_to_send,
    )
    func = message.reply if llm_reply.success else message.answer
    await func(llm_reply.text)
    await react(llm_reply.success, message)


@router.message(config.filter_is_admin, Command(commands=['admin_stats']))
async def handle_stats_command(message: types.Message, command: types.CommandObject):
    logger.info('Command /admin_stats received from chat_id=%s user=%s', message.chat.id, message.from_user.username)
    stats = message_store.fetch_stats(keys_pattern='matvey-3000:history:*')
    total_chats = len(config)
    logger.debug('Admin stats: total_keys=%d, total_chats=%d', len(stats), total_chats)
    response = f'Total keys in storage: {len(stats)}'
    per_chat = '\n'.join(f'{key}: {count}' for key, count in stats)
    await message.reply(
        '\n'.join(['[ADMIN]', response, '===', per_chat, f'Total chats: {total_chats}'])
    )


@router.message(
    config.filter_summary_enabled,
    Command(commands=['samari', 'sammari', 'sum', 'sosum']),
)
async def handle_summary_command(message: types.Message, command: types.CommandObject):
    logger.info('Command /%s (summary) received from chat_id=%s user=%s', command.command, message.chat.id, message.from_user.username)
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
    limit = command.args
    limit = -1 if limit is None else int(command.args)
    logger.debug('Fetching messages for summary, tag=%s, limit=%d', tag, limit)
    messages = message_store.fetch_messages(key=tag, limit=limit)
    # encoding = tiktoken.get_encoding("cl100k_base")
    encoding = tiktoken.encoding_for_model(config.model_for_chat_id(message.chat.id))
    total = len(messages)
    logger.info('Starting summary generation for chat_id=%s, message_count=%d', message.chat.id, total)
    info_message = await message.answer(f'🤖 Обрабатываю {total} сообщений')
    # full_text = '\n'.join(m.text for m in messages)

    max_chunk_size = 16385

    def L(x: str) -> int:
        return len(encoding.encode(x))

    def chunk_it(texts: list[str]) -> list[str]:
        chunks = []
        current_chunk = ""

        for tt in texts:
            if L(current_chunk) + L(tt) < max_chunk_size:
                current_chunk += tt + "\n"
            else:
                chunks.append(current_chunk.strip())
                current_chunk = tt + "\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    chunks = chunk_it(texts=map(str, messages))
    logger.debug('Split messages into %d chunks for chat_id=%s', len(chunks), message.chat.id)
    progress = await message.answer(f'Обрабатываю 0/{len(chunks)} чанков')

    # get summary for each chunk
    async def get_summaries(chunks, entity='чанк'):
        prompt = """
You are a helpful assistant who recaps everything that happened in this chat relying on its log.
You use Russian language only, and try to do each recap in no more than 25 sentences, but don't use generalisations too often.
The text is written by other chat members. You retell the most interesting phrases and actions, starting with the name of the actor.
You never lose a chronology of replies and never repeat yourself, while trying to balance out amount of participants' input.
You seldom mention texts produced by chatbots, such as you.
Sometimes you try to be funny by mixing up events and phrases, but never overdo it.
        """
        prompt = prompt.strip()
        total_chunks = len(chunks)
        summaries = []
        for i, chunk in enumerate(chunks, start=1):
            mm = [('system', prompt), ('user', chunk)]
            await progress.edit_text(f'Обрабатываю {entity} {i}/{total_chunks}')
            await message.chat.do('typing')
            llm_reply = await TextResponse.generate(
                config=config,
                chat_id=message.chat.id,
                messages=mm,
            )
            summaries.append(llm_reply.text)
            await asyncio.sleep(0.5)
        return summaries

    summaries = await get_summaries(chunks)
    logger.debug('Generated %d summaries for chat_id=%s', len(summaries), message.chat.id)

    final_prompt = """
You are a helpful assistant who recaps everything that happened in this chat relying on its log.
You use Russian language only, and try to do each recap in no more than 25 sentences, but don't use generalisations too often.
The text is written by other chat members. You retell the most interesting phrases and actions, starting with the name of the actor.
You never lose a chronology of replies and never repeat yourself, while trying to balance out amount of participants' input.
You seldom mention texts produced by chatbots, such as you.
Sometimes you try to be funny by mixing up events and phrases, but never overdo it.
After you recap everything, highlight three most outstanding facts or points from the text in a separate paragraph, while not repeating your own words.
"""
    final_prompt = final_prompt.strip()
    L_final_prompt = L(final_prompt)

    final_summary = '\n'.join(summaries)
    while L(final_summary) > (max_chunk_size - L_final_prompt):
        final_summary = '\n'.join(summaries)
        chunks = chunk_it(texts=summaries)
        summaries = await get_summaries(chunks, entity='предсаммари')
        final_summary = '\n'.join(summaries)

    await progress.delete()

    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=[('system', final_prompt), ('user', final_summary)],
    )

    await info_message.delete()

    logger.info('Summary generation completed for chat_id=%s, success=%s', message.chat.id, llm_reply.success)
    await message.reply(llm_reply.text)
    await react(llm_reply.success, message)


@router.message(F.text, config.filter_chat_allowed)
async def handle_text_message(message: types.Message):
    logger.debug('Text message received from chat_id=%s user=%s, text_length=%d',
                 message.chat.id, message.from_user.username, len(message.text or ''))
    chat_config = config[message.chat.id]
    save_messages = chat_config.save_messages
    context_enabled = chat_config.context_enabled

    # Define tag for potential use in context building and message saving
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'

    # if last message is a single word, ignore it
    args = message.text
    args = args.split()
    if len(args) == 1:
        logger.debug('Ignoring single-word message from chat_id=%s', message.chat.id)
        return

    # Determine if we should respond
    should_respond = False

    # Check if this is a reply thread (backward compatibility)
    message_chain = extract_message_chain(message, bot.id)
    has_bot_in_thread = any(role == 'assistant' for role, _ in message_chain)

    if has_bot_in_thread:
        # Bot is part of the thread, respond
        should_respond = True
        logger.debug('Responding to reply thread in chat_id=%s', message.chat.id)
    elif len(message_chain) > 1 and random.random() < 0.95:
        # Thread without bot, mostly ignore
        logger.debug('Ignoring thread without bot in chat_id=%s', message.chat.id)
        return
    elif message.chat.id < 0:
        # Group chat - only respond if mentioned
        if any(config.me in x for x in args):
            should_respond = True
            logger.debug('Responding to mention in group chat_id=%s', message.chat.id)
    else:
        # Private chat - always respond
        should_respond = True
        logger.debug('Responding to private chat_id=%s', message.chat.id)

    if not should_respond:
        logger.debug('Not responding to message in chat_id=%s', message.chat.id)
        return

    # Build context for LLM
    system_prompt = config.prompt_tuple_for_chat(message.chat.id)

    if context_enabled and save_messages:
        # Use Redis-based conversation history
        max_context = chat_config.max_context_messages
        logger.debug('Building context from Redis for chat_id=%s, max_context=%d', message.chat.id, max_context)
        messages_to_send = message_store.build_context_messages(
            key=tag,
            limit=max_context,
            bot_username=config.me_strip_lower,
            system_prompt=system_prompt,
            max_tokens=4000,
        )
        # Add current message (not yet in Redis)
        messages_to_send.append(('user', message.text))
        logger.debug('Context built for chat_id=%s, total_messages=%d', message.chat.id, len(messages_to_send))
    else:
        # Fallback to thread-based context
        logger.debug('Using thread-based context for chat_id=%s, chain_length=%d', message.chat.id, len(message_chain))
        messages_to_send = [
            system_prompt,
            *message_chain,
        ]

    await message.chat.do('typing')

    provider = config.provider_for_chat_id(message.chat.id)
    model = config.model_for_chat_id(message.chat.id)
    logger.info('Generating LLM response for chat_id=%s, provider=%s, model=%s, context_messages=%d',
                message.chat.id, provider, model, len(messages_to_send))

    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=messages_to_send,
    )

    if llm_reply.success:
        logger.info('LLM response generated successfully for chat_id=%s, response_length=%d',
                    message.chat.id, len(llm_reply.text))
    else:
        logger.warning('LLM response failed for chat_id=%s, error=%s', message.chat.id, llm_reply.text[:100])

    func = message.reply if llm_reply.success else message.answer
    await func(llm_reply.text)

    if save_messages:
        # Save user message first
        user_msg = StoredChatMessage.from_tg_message(message)
        message_store.save(tag, user_msg)

        # Then save bot response
        bot_msg = StoredChatMessage(
            chat_name=message.chat.full_name,
            from_username=config.me_strip_lower,
            from_full_name='BOT',
            text=llm_reply.text,
            timestamp=int(time.time()),
        )
        message_store.save(tag, bot_msg)
        logger.debug('Saved user and bot messages to Redis for chat_id=%s', message.chat.id)

    await react(llm_reply.success, message)


async def main():
    logger.info('Starting bot with config version=%s, bot_username=%s', config.version, config.me)
    logger.info('Configured chats: %d, git_sha=%s', len(config), config.git_sha)
    dp = Dispatcher()
    dp.include_router(router)
    logger.info('Bot polling started')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
