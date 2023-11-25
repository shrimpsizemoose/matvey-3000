from __future__ import annotations

import textwrap
import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

from aiogram import html


@dataclass
class Config:
    setup: list[dict[str, str]] | dict[str, Any]
    allowed_chat_id: list[int]
    me: str
    model_chatgpt: str
    model_anthropic: str
    version: int

    VERSION_ONE = 1
    VERSION_TWO = 2
    VERSION_THREE = 3

    PROVIDER_OPENAI = 'openai'
    PROVIDER_ANTHROPIC = 'anthropic'

    @classmethod
    def read_yaml(cls, path) -> Config:
        with pathlib.Path(path).open() as fp:
            config = yaml.safe_load(fp)
        return cls(
            setup=config['setup'],
            me=config['me'],
            model_chatgpt=config.get('model_chatgpt', config.get('model')),
            model_anthropic=config.get('model_anthropic', config.get('model')),
            allowed_chat_id=config['allowed_chat_id'],
            version=config.get('version', cls.VERSION_ONE),
        )

    def model_for_provider(self, provider):
        # this should be per-chat setting???
        if self.version < self.VERSION_THREE:
            return self.model_chatgpt
        return {
            self.PROVIDER_OPENAI: self.model_chatgpt,
            self.PROVIDER_ANTHROPIC: self.model_anthropic
        }[provider]

    async def filter_chat_allowed(self, message) -> bool:
        return message.chat.id in self.allowed_chat_id

    def override_prompt_for_chat(self, chat_id, new_prompt) -> bool:
        if self.version < self.VERSION_TWO:
            return False
        self.setup['prompts'][chat_id] = new_prompt
        return True

    def rich_info(self, chat_id) -> str:
        _, prompt = self.prompt_message_for_user(chat_id)
        provider = self.provider_for_chat_id(chat_id)
        model = self.model_for_provider(provider)
        lines = [
            'Current prompt:\n',
            html.code(prompt),
            f'\nconfig version {html.underline(self.version)}',
            f'model: {html.underline(model)}',
            f'provider: {html.underline(provider)}',
        ]
        return '\n'.join(lines)

    def provider_for_chat_id(self, chat_id) -> str:
        if self.version < self.VERSION_THREE:
            return self.PROVIDER_OPENAI
        default = self.setup['providers']['default']
        return self.setup['providers'].get(chat_id, default)

    def override_provider_for_chat_id(self, chat_id, provider) -> str:
        if self.version < self.VERSION_THREE:
            return self.PROVIDER_OPENAI
        self.setup['providers'][chat_id] = provider

    def model_for_chat_id(self, chat_id) -> str:
        provider = self.provider_for_chat_id(chat_id)
        return self.model_for_provider(provider)

    def prompt_message_for_user(self, chat_id) -> tuple[str, str]:
        """
            for versions below version 2 always return the main setup system message
            assumptions: there's only one "role": "system" message in setup for default
        """
        if self.version == self.VERSION_TWO:
            default = self.setup['default_prompt']
            prompts = self.setup.get('prompts', {chat_id: default})
            return ('system', prompts.get(chat_id, default))
        if self.version == self.VERSION_THREE:
            default = self.setup['prompts']['default']
            return ('system', self.setup['prompts'].get(chat_id, default))

        return (
            'system',
            [
                msg for msg in self.setup
                if msg['role'] == 'system'
            ][-1]['content'],
        )

    def fetch_translation_prompt_message(self, target_language) -> str:
        en_to_ru = """
        You are a bot that just translates all messages from English to Russian,
        I want you to also fix grammatical and spelling errors you find along the way.
        Capture the style of the original as you can. Answer first with corrected original English text.
        Then, add an empty line and then add translation to Russian.
        Original English message phrase you are translating should go first.
        If there are multiple translations, provide two most common
        If there are any style suggestions or explanations, add them after a line break.
        For example, when I write:
          To h'll wit it
        You respond:
          EN: To hell with it
          RU: К чёрту это

          Подобное выражение означает фрустрацию и усталость происходящим.
          Аккуратно, выражение немного вульгарно
        """
        en_to_ru = textwrap.dedent(en_to_ru.strip('\n'))

        ru_to_en = """
        You are a bot that just translates all messages from Russian to English,
        I want you to also fix grammatical and spelling errors you find along the way.
        In your translation, try to capture the style of the original as you can.
        Start your response with corrected original Russian text.
        Then, add an empty line and then add translation to English.
        Original Russian message phrase you are translating should go first.
        If there are multiple translations, provide two most common
        If there are any style suggestions or explanations, add them after a line break.
        For example, when I write:
          Ля какя цаца
        You respond:
          RU: Ля какая цаца
          EN: Wow, what a sight!
          EN: Wow, what a thing!

          This phrase can be used to express surprise at something unusial, interesting or attractive
        """
        ru_to_en = textwrap.dedent(ru_to_en.strip('\n'))
        prompt = {'ru': en_to_ru, 'en': ru_to_en}.get(target_language)
        return {'role': 'assistant', 'content': prompt}
