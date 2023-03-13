from __future__ import annotations

import collections
import os
import pathlib
import logging
from dataclasses import dataclass

import openai
import yaml
from aiogram import Bot, Dispatcher, executor, types

openai.api_key = os.getenv('OPENAI_API_KEY')
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
YAML_CONFIG = os.getenv('BOT_CONFIG_YAML')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dataclass
class Config:
    setup: list[dict[str, str]]
    allowed_chat_id: list[int]
    me: str
    model: str

    @classmethod
    def read_yaml(cls, fname) -> Config:
        with pathlib.Path(fname).open() as fp:
            config = yaml.safe_load(fp)
        return cls(
            setup=config['setup'],
            me=config['me'],
            model=config['model'],
            allowed_chat_id=config['allowed_chat_id'],
        )

config = Config.read_yaml(YAML_CONFIG)


def extract_message_chain(last_message_in_thread: types.Message, bot_id: int):
    payload = collections.deque()
    cur = last_message_in_thread
    while cur is not None:
        try:
            tmp = cur.reply_to_message
            if tmp is not None:
                role = 'assistant' if tmp.from_user.id == bot_id else 'user'
                payload.appendleft((role, tmp.text))
                cur = tmp
            else:
                break
        except AttributeError:
            break
    payload.append(('user', last_message_in_thread.text))
    return [
        {'role': role, 'content': text}
        for role, text in payload
    ]


@dp.message_handler(commands=['blerb'])
async def dump_message_info(message: types.Message):
    print(message)
    print(message.chat.id)
    await message.reply(message.chat.id)


@dp.message_handler(lambda message: message.chat.id in config.allowed_chat_id)
async def send_chatgpt_response(message: types.Message):
    ## rich.print(message)

    # if last message is a single word, ignore it
    args = message.parse_entities()
    args = args.split()
    if len(args) == 1:
        return

    message_chain = extract_message_chain(message, bot.id)
    if len(message_chain) == 1 and message.chat.id < 0:
        if not any(config.me in x for x in args):
            # nobody mentioned me, so I shut up
            return
    else:
        # we are either in private messages, or there's a continuation of a thread
        pass

    messages_to_send = config.setup

    ## print(message_chain)
    ## print('processing a chain of', len(message_chain), 'messages in chat', message.chat.id)

    messages_to_send.extend(message_chain)

    await message.chat.do('typing')
    response = openai.ChatCompletion.create(model=config.model, messages=messages_to_send)
    await message.answer(response['choices'][0]['message']['content'])


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
