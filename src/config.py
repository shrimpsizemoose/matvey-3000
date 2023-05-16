from __future__ import annotations

import textwrap
import pathlib
from dataclasses import dataclass
from typing import Any

import yaml



@dataclass
class Config:
    setup: list[dict[str, str]] | dict[str, Any]
    allowed_chat_id: list[int]
    me: str
    model: str
    version: int

    VERSION_ONE = 1
    VERSION_TWO = 2

    @classmethod
    def read_yaml(cls, path) -> Config:
        with pathlib.Path(path).open() as fp:
            config = yaml.safe_load(fp)
        return cls(
            setup=config['setup'],
            me=config['me'],
            model=config['model'],
            allowed_chat_id=config['allowed_chat_id'],
            version=config.get('version', cls.VERSION_ONE),
        )

    async def filter_chat_allowed(self, message) -> bool:
        return message.chat.id in self.allowed_chat_id

    def override_prompt_for_chat(self, chat_id, new_prompt) -> bool:
        if self.version < self.VERSION_TWO:
            return False
        self.setup['prompts'][chat_id] = new_prompt
        return True

    def prompt_message_for_user(self, chat_id) -> dict[str, str]:
        """
            for versions below version 2 always return the main setup system message
            assumptions: there's only one "role": "system" message in setup for default
        """
        if self.version == self.VERSION_TWO:
            default = self.setup['default_prompt']
            prompts = self.setup.get('prompts', {chat_id: default})
            return {'role': 'system', 'content': prompts.get(chat_id, default)}

#        if (default := self.setup.get('default_prompt')) is not None:
#            return {'role': 'system', 'content': default}

        default = {'role': 'system'}
        for message in self.setup:
            if message['role'] == 'system':
                default['content'] = message['content']

        # if no message was found, don't add any defaults, because it's okay
        # to blow up from here: this means the given config is completely fucked up
        return default

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
