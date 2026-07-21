from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import openai

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ConversationResult:
    success: bool
    text: str


class ConversationProvider(Protocol):
    async def generate(
        self,
        model: str,
        messages: list[ChatMessage],
    ) -> ConversationResult: ...


class ConversationProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ConversationProvider] = {}

    def register(self, name: str, provider: ConversationProvider) -> None:
        if name in self._providers:
            raise ValueError(f'Conversation provider already registered: {name}')
        self._providers[name] = provider

    def get(self, name: str) -> ConversationProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ValueError(f'Unsupported conversation provider: {name}') from exc


class OpenAIConversationProvider:
    def __init__(self, client: openai.AsyncOpenAI) -> None:
        self._client = client

    async def generate(
        self,
        model: str,
        messages: list[ChatMessage],
    ) -> ConversationResult:
        logger.debug(
            'OpenAI request: model=%s, message_count=%d',
            model,
            len(messages),
        )
        payload = [
            {'role': message.role, 'content': message.content} for message in messages
        ]

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=payload,
            )
        except openai.RateLimitError as exc:
            logger.warning('OpenAI rate limit error: %s', exc)
            return ConversationResult(
                success=False,
                text=(
                    'Кажется я подустал и воткнулся в рейт-лимит. '
                    f'Давай сделаем перерыв ненадолго.\n\n{exc}'
                ),
            )
        except openai.BadRequestError as exc:
            logger.warning('OpenAI bad request error: %s', exc)
            return ConversationResult(
                success=False,
                text=f'Beep-bop, кажется я не умею отвечать на такие вопросы:\n\n{exc}',
            )
        except TimeoutError as exc:
            logger.error('OpenAI timeout error: %s', exc)
            return ConversationResult(
                success=False,
                text=(
                    'Кажется у меня сбоит сеть. Ты попробуй позже, '
                    f'а я пока схожу чаю выпью.\n\n{exc}'
                ),
            )

        text = response.choices[0].message.content
        logger.debug(
            'OpenAI response received: model=%s, response_length=%d',
            model,
            len(text),
        )
        return ConversationResult(success=True, text=text)
