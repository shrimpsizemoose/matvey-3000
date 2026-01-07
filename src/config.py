from __future__ import annotations

import functools
import logging
import os
import pathlib
import tomllib
from dataclasses import dataclass

from aiogram import types


logger = logging.getLogger(__name__)


@dataclass
class ChatConfig:
    chat_id: int
    prompt: str
    provider: str
    allowed: bool
    who: str
    is_admin: bool = False
    save_messages: bool = False
    summary_enabled: bool = False
    voice_enabled: bool = False
    disabled_commands: list[str] | None = None
    context_enabled: bool = True
    max_context_messages: int = 10
    tts_voice: str = 'alloy'

    @classmethod
    def just_no(cls, chat_id, provider, disabled_commands):
        return cls(
            chat_id=chat_id,
            prompt="you are silent mute and don't talk to anyone at all",
            provider=provider,
            allowed=False,
            is_admin=False,
            save_messages=False,
            summary_enabled=False,
            voice_enabled=False,
            disabled_commands=disabled_commands,
            who="i don't know who",
            context_enabled=False,
            max_context_messages=0,
        )


@dataclass
class Config:
    me: str
    version: int
    configs: ChatConfig
    default_prompt: str
    default_provider: str
    allowed_chat_id: list[int]

    git_sha: str

    model_chatgpt: str
    model_anthropic: str
    model_yandexgpt: str

    en_to_ru_prompt: str
    ru_to_en_prompt: str
    positive_emojis: str
    negative_emojis: str

    PROVIDER_OPENAI = 'openai'
    PROVIDER_ANTHROPIC = 'anthropic'
    PROVIDER_YANDEXGPT = 'yandexgpt'

    TTS_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']

    REPLICATE_MODEL_EDIT = 'timothybrooks/instruct-pix2pix:30c1d0b916a6f8efce20493f5d61ee27491ab2a60437c13c588468b9810ec23f'
    REPLICATE_MODEL_REMOVE_BG = 'lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1'

    ALL_COMMANDS = [
        '/pic',
        '/pic3',
        '/pik',
        '/edit',
        '/remove',
        '/replace',
        '/remove_bg',
        '/background',
        '/bg',
        '/reimagine',
        '/tts',
        '/cancel',
        '/blerb',
        '/mode_claude',
        '/mode_chatgpt',
        '/mode_yandex',
        '/ru',
        '/en',
        '/prompt',
        '/sammari',
        '/sum',
        '/samari',
        '/sosum',
        '/new_chat',
    ]

    @classmethod
    def read_toml(cls, path) -> Config:
        logger.info('Loading config from %s', path)
        with pathlib.Path(path).open('rb') as fp:
            config = tomllib.load(fp)

        default_prompt = config['defaults']['prompt']
        default_provider = config['defaults']['provider']
        allowed_chat_ids = [chat['id'] for chat in config['chats']['allowed']]
        per_chat_configs = {
            chat['id']: ChatConfig(
                chat_id=chat['id'],
                prompt=chat.get('prompt', default_prompt).strip(),
                provider=chat.get('provider', default_provider),
                allowed=True,
                who=chat['who'],
                is_admin=chat.get('is_admin', False),
                save_messages=chat.get('save_messages', False),
                summary_enabled=chat.get('summary_enabled', False),
                voice_enabled=chat.get('voice_enabled', False),
                disabled_commands=chat.get('disabled_commands', []),
                context_enabled=chat.get('context_enabled', True),
                max_context_messages=chat.get('max_context_messages', 10),
                tts_voice=chat.get('tts_voice', 'alloy'),
            )
            for chat in config['chats']['allowed']
        }

        git_sha = os.getenv('GIT_SHA_ENV', 'Unknown')

        logger.info('Config loaded: version=%s, bot=%s, allowed_chats=%d, default_provider=%s',
                    config['version'], config['me'], len(allowed_chat_ids), default_provider)
        logger.debug('Allowed chat IDs: %s', allowed_chat_ids)

        return cls(
            me=config['me'],
            version=config['version'],
            configs=per_chat_configs,
            default_prompt=default_prompt,
            default_provider=default_provider,
            allowed_chat_id=allowed_chat_ids,
            git_sha=git_sha,
            model_chatgpt=config['models']['chatgpt'],
            model_anthropic=config['models']['anthropic'],
            model_yandexgpt=config['models']['yandexgpt'],
            en_to_ru_prompt=config['translations']['en_to_ru'],
            ru_to_en_prompt=config['translations']['ru_to_en'],
            positive_emojis=config['positive_emojis'],
            negative_emojis=config['negative_emojis'],
        )

    def __getitem__(self, chat_id) -> ChatConfig:
        config = self.configs.get(chat_id)
        if config is None:
            return ChatConfig.just_no(
                chat_id=chat_id,
                provider=self.default_provider,
                disabled_commands=[],  # self.ALL_COMMANDS,
            )
        return config

    def __len__(self) -> int:
        return len(self.configs)

    @functools.cached_property
    def me_strip_lower(self):
        return self.me.lstrip('@').lower()

    def model_for_provider(self, provider):
        # this should be per-chat setting???
        return {
            self.PROVIDER_OPENAI: self.model_chatgpt,
            self.PROVIDER_ANTHROPIC: self.model_anthropic,
            self.PROVIDER_YANDEXGPT: self.model_yandexgpt,
        }[provider]

    async def filter_chat_allowed(self, message) -> bool:
        allowed = message.chat.id in self.allowed_chat_id
        if not allowed:
            logger.debug('Chat not allowed: chat_id=%s', message.chat.id)
        return allowed

    async def filter_command_not_disabled_for_chat(self, message) -> bool:
        if message.chat.id not in self.allowed_chat_id:
            logger.debug('Chat not in config: chat_id=%s', message.chat.id)
            return False
        if not self[message.chat.id].disabled_commands:
            return True
        ee = message.entities or []
        commands = [e.extract_from(message.text) for e in ee if e.type == 'bot_command']
        if not commands:
            return True
        if commands[0] in self[message.chat.id].disabled_commands:
            logger.debug('Command disabled for chat: command=%s, chat_id=%s', commands[0], message.chat.id)
            react = types.reaction_type_emoji.ReactionTypeEmoji(
                type='emoji', emoji='🙊'
            )
            await message.react(reaction=[react])
            return False
        return True

    async def filter_is_admin(self, message) -> bool:
        is_admin = self[message.chat.id].is_admin
        logger.debug('Admin check for chat_id=%s: is_admin=%s', message.chat.id, is_admin)
        return is_admin

    async def filter_summary_enabled(self, message) -> bool:
        enabled = self[message.chat.id].summary_enabled
        logger.debug('Summary enabled check for chat_id=%s: enabled=%s', message.chat.id, enabled)
        return enabled

    async def filter_voice_enabled(self, message) -> bool:
        enabled = self[message.chat.id].voice_enabled
        logger.debug('Voice enabled check for chat_id=%s: enabled=%s', message.chat.id, enabled)
        return enabled

    def override_prompt_for_chat(self, chat_id, new_prompt) -> bool:
        logger.info('Overriding prompt for chat_id=%s, new_prompt_length=%d', chat_id, len(new_prompt))
        self.configs[chat_id].prompt = new_prompt
        return True

    def rich_info(self, chat_id) -> str:
        from aiogram import html

        config = self.configs[chat_id]

        provider = config.provider
        model = self.model_for_provider(provider)
        lines = [
            'Current prompt:\n',
            html.code(config.prompt),
            f'\nconfig version {html.underline(self.version)}',
            f'model: {html.underline(model)}',
            f'provider: {html.underline(provider)}',
            f'saving messages: {"YES" if config.save_messages else "NO"}',
            f'git sha: {html.underline(self.git_sha)}',
        ]
        return '\n'.join(lines)

    def provider_for_chat_id(self, chat_id) -> str:
        provider = self.configs[chat_id].provider
        logger.debug('Provider for chat_id=%s: %s', chat_id, provider)
        return provider

    def override_provider_for_chat_id(self, chat_id, new_provider) -> str:
        old_provider = self.configs[chat_id].provider
        self.configs[chat_id].provider = new_provider
        logger.info('Provider changed for chat_id=%s: %s -> %s', chat_id, old_provider, new_provider)

    def model_for_chat_id(self, chat_id) -> str:
        provider = self.provider_for_chat_id(chat_id)
        return self.model_for_provider(provider)

    def prompt_tuple_for_chat(self, chat_id) -> tuple[str, str]:
        return ('system', self.configs[chat_id].prompt)

    def fetch_translation_prompt_tuple(self, target_language) -> str:
        prompt = {'ru': self.en_to_ru_prompt, 'en': self.ru_to_en_prompt}.get(
            target_language
        )
        return ('system', prompt)
