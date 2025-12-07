from __future__ import annotations

import asyncio
import base64
import collections
import logging
import os
import random
import time

import openai
import tiktoken

from aiogram import F
from aiogram import Bot, Dispatcher, Router, html, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

from config import Config
from chat_completions import TextResponse, ImageResponse
from message_store import MessageStore, StoredChatMessage


API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

logging.basicConfig(level=logging.INFO)
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
    logger.info(f'incoming blerb from {message.chat.id}')
    await message.reply(f'chat id: {html.code(message.chat.id)}')


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['mode_claude'], ignore_mention=True),
)
async def switch_to_claude(message: types.Message):
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_ANTHROPIC)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_ANTHROPIC}!')


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['mode_chatgpt'], ignore_mention=True),
)
async def switch_to_chatgpt(message: types.Message):
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_OPENAI)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_OPENAI}!')


@router.message(
    config.filter_command_not_disabled_for_chat,
    Command(commands=['mode_yandex'], ignore_mention=True),
)
async def switch_to_yandexgpt(message: types.Message):
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_YANDEXGPT)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_YANDEXGPT}!')


@router.message(config.filter_chat_allowed, Command(commands=['prompt']))
async def dump_set_prompt(message: types.Message, command: types.CommandObject):
    new_prompt = command.args
    if not new_prompt:
        await message.reply(config.rich_info(message.chat.id))
        return

    success = config.override_prompt_for_chat(message.chat.id, new_prompt)
    if success:
        await message.answer(
            'okie-dokie 👌 prompt изменён но нет никаких гарантий что это надолго'
        )
    else:
        await message.answer('nope 🙅')


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=['new_chat']),
)
async def handle_new_chat(message: types.Message):
    """Clear conversation history and start fresh."""
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
    deleted_count = message_store.clear_conversation_history(tag)
    
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
    prompt = command.args
    await message.chat.do('upload_photo')
    try:
        response = await ImageResponse.generate(prompt, mode='dall-e')
    except openai.BadRequestError:
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
        await message.chat.do('upload_photo')
        image_from_url = types.URLInputFile(response.b64_or_url)
        caption = f'DALL-E2 prompt: {prompt}'
        await message.answer_photo(image_from_url, caption=caption)
        await react(success=True, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=['pik']),
)
async def gimme_pikk(message: types.Message, command: types.CommandObject):
    if command.command in config[message.chat.id].disabled_commands:
        react(False, message)
        return
    prompt = command.args
    await message.chat.do('upload_photo')
    try:
        response = await ImageResponse.generate(prompt, mode='kandinski')
    except openai.BadRequestError:
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
            # await message.reply(json.dumps(response, indent=4))
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
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=['ru', 'en']),
)
async def translate_ruen(message: types.Message, command: types.CommandObject):
    if command.command in config[message.chat.id].disabled_commands:
        react(False, message)
        return
    prompt_tuple = config.fetch_translation_prompt_tuple(command.command)
    messages_to_send = [prompt_tuple, ('user', command.args)]
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
    stats = message_store.fetch_stats(keys_pattern='matvey-3000:history:*')
    total_chats = len(config)
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
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
    limit = command.args
    limit = -1 if limit is None else int(command.args)
    messages = message_store.fetch_messages(key=tag, limit=limit)
    # encoding = tiktoken.get_encoding("cl100k_base")
    encoding = tiktoken.encoding_for_model(config.model_for_chat_id(message.chat.id))
    total = len(messages)
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

    await message.reply(llm_reply.text)
    await react(llm_reply.success, message)


@router.message(F.text, config.filter_chat_allowed)
async def handle_text_message(message: types.Message):
    chat_config = config[message.chat.id]
    save_messages = chat_config.save_messages
    context_enabled = chat_config.context_enabled
    
    # Define tag for potential use in context building and message saving
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
    
    if save_messages:
        msg = StoredChatMessage.from_tg_message(message)
        message_store.save(tag, msg)

    # if last message is a single word, ignore it
    args = message.text
    args = args.split()
    if len(args) == 1:
        return

    # Determine if we should respond
    should_respond = False
    
    # Check if this is a reply thread (backward compatibility)
    message_chain = extract_message_chain(message, bot.id)
    has_bot_in_thread = any(role == 'assistant' for role, _ in message_chain)
    
    if has_bot_in_thread:
        # Bot is part of the thread, respond
        should_respond = True
    elif len(message_chain) > 1 and random.random() < 0.95:
        # Thread without bot, mostly ignore
        return
    elif message.chat.id < 0:
        # Group chat - only respond if mentioned
        if any(config.me in x for x in args):
            should_respond = True
    else:
        # Private chat - always respond
        should_respond = True
    
    if not should_respond:
        return

    # Build context for LLM
    system_prompt = config.prompt_tuple_for_chat(message.chat.id)
    
    if context_enabled and save_messages:
        # Use Redis-based conversation history
        max_context = chat_config.max_context_messages
        messages_to_send = message_store.build_context_messages(
            key=tag,
            limit=max_context,
            bot_username=config.me_strip_lower,
            system_prompt=system_prompt,
            max_tokens=4000,
        )
        # Always add current message (it was just saved to Redis)
        messages_to_send.append(('user', message.text))
    else:
        # Fallback to thread-based context
        messages_to_send = [
            system_prompt,
            *message_chain,
        ]

    await message.chat.do('typing')

    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=messages_to_send,
    )
    func = message.reply if llm_reply.success else message.answer
    await func(llm_reply.text)

    if save_messages:
        msg = StoredChatMessage(
            chat_name=message.chat.full_name,
            from_username=config.me_strip_lower,
            from_full_name='BOT',
            text=llm_reply.text,
            timestamp=int(time.time()),
        )
        message_store.save(tag, msg)

    await react(llm_reply.success, message)


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
