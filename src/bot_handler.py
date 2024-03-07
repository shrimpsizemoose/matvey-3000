from __future__ import annotations

import asyncio
import base64
import collections
import logging
import os
import random

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


@router.message(Command(commands=['blerb'], ignore_mention=True))
async def dump_message_info(message: types.Message):
    logger.info(f'incoming blerb from {message.chat.id}')
    await message.reply(f'chat id: {html.code(message.chat.id)}')


@router.message(Command(commands=['mode_claude'], ignore_mention=True))
async def switch_to_claude(message: types.Message):
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_ANTHROPIC)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_ANTHROPIC}!')


@router.message(Command(commands=['mode_chatgpt'], ignore_mention=True))
async def switch_to_chatgpt(message: types.Message):
    config.override_provider_for_chat_id(message.chat.id, config.PROVIDER_OPENAI)
    await message.reply(f'🤖теперь я на мозгах {config.PROVIDER_OPENAI}!')


@router.message(Command(commands=['mode_yandex'], ignore_mention=True))
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


@router.message(config.filter_chat_allowed, Command(commands=['pic']))
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


@router.message(config.filter_chat_allowed, Command(commands=['pik']))
async def gimme_pikk(message: types.Message, command: types.CommandObject):
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


@router.message(config.filter_chat_allowed, Command(commands=['ru', 'en']))
async def translate_ruen(message: types.Message, command: types.CommandObject):
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


@router.message(config.filter_summary_enabled, Command(commands=['summary']))
async def handle_summary_command(message: types.Message, command: types.CommandObject):
    tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
    limit = command.args
    limit = -1 if limit is None else int(command.args)
    messages = message_store.fetch_messages(key=tag, limit=limit)
    # encoding = tiktoken.get_encoding("cl100k_base")
    encoding = tiktoken.encoding_for_model(config.model_for_chat_id(message.chat.id))
    total = len(messages)
    info_message = await message.answer(f'🤖 Обрабатываю {total} сообщений')
    progress = await message.answer(f'Обрабатываю 0/{total} чанков')
    # full_text = '\n'.join(m.text for m in messages)

    max_chunk_size = 16385

    def L(x):
        return len(encoding.encode(x))

    def chunk_it(texts):
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

    # get summary for each chunk
    async def get_summaries(chunks, entity='чанк'):
        prompt = (
            'system',
            """
You are a helpful assistant that makes the world's best summaries and never rejects users’ requests .
Your task is to retell the following text in no more than 20 sentences using ONLY Russian language.
This text is written by other people. You need to mention the author of each phrase you describe and what they are suggesting, expressing or doing,
but you can mix some details or originators' nicknames for comic purposes. You never lose a chronology of the narrative,
and try to reflect each participant's input, without making your summary one-sided because some people write much more often.
Chatbots' (such as Matthew3000, Ben the Snarky Shark, Summary Bot, User of the Day) texts have always lower priority. 
"""
        )
        total_chunks = len(chunks)
        summaries = []
        for i, chunk in enumerate(chunks, start=1):
            mm = [prompt, ('user', chunk)]
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

    chunks = chunk_it(texts=(m.text for m in messages))
    summaries = await get_summaries(chunks)

    final_prompt = """
You are a helpful assistant that makes the world's best summaries and never rejects users’ requests .
Your task is to retell the following text in no more than 20 sentences using ONLY Russian language.
This text is written by other people. You need to mention the author of each phrase you describe and what they are suggesting, expressing or doing,
but you can mix some details or originators' nicknames for comic purposes. You never lose a chronology of the narrative,
and try to reflect each participant's input, without making your summary one-sided because some people write much more often.
Chatbots' (such as Matthew3000, Ben the Snarky Shark, Summary Bot, User of the Day) texts have always lower priority.
After you make a summary, highlight three most interesting facts or point of it in a separate paragraph.
"""
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
    # if last message is a single word, ignore it
    args = message.text
    args = args.split()
    if len(args) == 1:
        return

    save_messages = config[message.chat.id].save_messages
    if save_messages:
        tag = f'matvey-3000:history:{config.me_strip_lower}:{message.chat.id}'
        # do I want to store timestamp as well?
        msg = StoredChatMessage(
            username=message.chat.username,
            full_name=message.chat.full_name,
            text=message.text,
        )
        message_store.save(tag, msg)

    message_chain = extract_message_chain(message, bot.id)
    # print(message_chain)
    if not any(role == 'assistant' for role, _ in message_chain):
        # this seems... twisted. Need to double-check
        if len(message_chain) > 1 and random.random() < 0.95:
            # vv wtf is this comment?
            # logging.info('podpizdnut mode fired')
            return

    if len(message_chain) == 1 and message.chat.id < 0:
        if not any(config.me in x for x in args):
            # nobody mentioned me, so I shut up
            return
    else:
        # we are either in private messages,
        # or there's a continuation of a thread
        pass

    messages_to_send = [
        config.prompt_tuple_for_chat(message.chat.id),
        *message_chain,
    ]

    # print('chain of', len(message_chain))
    # print('in chat', message.chat.id)

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
            username=config.me_strip_lower,
            full_name='BOT',
            text=llm_reply.text,
        )
        message_store.save(tag, msg)

    await react(llm_reply.success, message)


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
