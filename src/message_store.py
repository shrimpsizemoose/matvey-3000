from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

import redis
import tiktoken


logger = logging.getLogger(__name__)


CUTOFF = 2000


@dataclass
class StoredChatMessage:
    chat_name: str
    from_username: str
    from_full_name: str
    timestamp: int
    text: str
    #    raw: str

    def serialize(self):
        return json.dumps(asdict(self), ensure_ascii=False)

    def __str__(self):
        tag = f'{self.from_username}'
        if self.from_full_name:
            tag = f'{self.from_full_name} <{self.from_username}>'
        return f'{tag} [at {self.timestamp}]: {self.text}'

    @classmethod
    def deserialize(cls, serialized_dict: str | dict):
        if isinstance(serialized_dict, (str, bytes)):
            serialized_dict = json.loads(serialized_dict)
        obj = cls(**serialized_dict)
        obj.timestamp = int(obj.timestamp)
        return obj

    @classmethod
    def from_tg_message(cls, message):
        from_user = message.from_user

        return cls(
            chat_name=message.chat.full_name,
            from_username=from_user.username,
            from_full_name=from_user.full_name,
            timestamp=int(message.date.timestamp()),
            text=message.text,
            # raw=message.model_dump_json(),
        )


class MessageStore:
    def __init__(self, redis_url: str):
        self.redis_conn = redis.from_url(redis_url)
        logger.info('Redis message store initialized: url=%s', redis_url.split('@')[-1] if '@' in redis_url else redis_url)

    @classmethod
    def from_env(cls) -> MessageStore:
        url = os.getenv('REDIS_URL')
        logger.debug('Creating MessageStore from environment variable REDIS_URL')
        return cls(url)

    def save(self, tag: str, message: StoredChatMessage):
        # might need to have a deeper per-hour or per-day split
        self.redis_conn.rpush(tag, message.serialize())
        list_len = self.redis_conn.llen(tag)
        logger.debug('Message saved: tag=%s, from=%s, list_len=%d', tag, message.from_username, list_len)
        if list_len > CUTOFF:
            self.redis_conn.ltrim(tag, 0, CUTOFF)
            logger.debug('List trimmed to CUTOFF=%d for tag=%s', CUTOFF, tag)

    def fetch_stats(self, keys_pattern: str) -> list[tuple[str, int]]:
        logger.debug('Fetching stats for pattern: %s', keys_pattern)
        keys = self.redis_conn.keys(keys_pattern)
        stats = [
            (key.decode(), self.redis_conn.llen(key))
            for key in keys
            if self.redis_conn.type(key) == b'list'  # noqa
        ]
        logger.debug('Stats fetched: %d keys found', len(stats))
        return stats

    def fetch_messages(
        self, key: str, limit: int, raw: bool = False
    ) -> list[StoredChatMessage] | list[bytes]:
        logger.debug('Fetching messages: key=%s, limit=%d, raw=%s', key, limit, raw)
        messages = self.redis_conn.lrange(key, -limit, -1)
        logger.debug('Fetched %d messages from key=%s', len(messages), key)
        if raw:
            return messages

        return list(map(StoredChatMessage.deserialize, messages))

    def fetch_conversation_history(
        self, key: str, limit: int, bot_username: str
    ) -> list[tuple[str, str]]:
        """
        Fetch recent conversation history and convert to (role, text) tuples.

        Args:
            key: Redis key for the chat history
            limit: Maximum number of messages to fetch
            bot_username: Bot's username to identify assistant messages

        Returns:
            List of (role, text) tuples where role is 'user' or 'assistant'
        """
        logger.debug('Fetching conversation history: key=%s, limit=%d', key, limit)
        messages = self.fetch_messages(key=key, limit=limit, raw=False)
        conversation = []

        for msg in messages:
            # Determine role based on username
            role = 'assistant' if msg.from_username == bot_username else 'user'
            conversation.append((role, msg.text))

        logger.debug('Conversation history fetched: %d messages', len(conversation))
        return conversation

    def clear_conversation_history(self, key: str) -> int:
        """
        Clear all conversation history for a given chat.

        Args:
            key: Redis key for the chat history

        Returns:
            Number of messages deleted
        """
        count = self.redis_conn.llen(key)
        self.redis_conn.delete(key)
        logger.info('Conversation history cleared: key=%s, messages_deleted=%d', key, count)
        return count

    def build_context_messages(
        self,
        key: str,
        limit: int,
        bot_username: str,
        system_prompt: tuple[str, str],
        max_tokens: int = 4000,
        encoding_name: str = "cl100k_base",
    ) -> list[tuple[str, str]]:
        """
        Build complete context for LLM including system prompt and recent history.
        Ensures token limit is not exceeded.

        Args:
            key: Redis key for the chat history
            limit: Maximum number of messages to fetch
            bot_username: Bot's username to identify assistant messages
            system_prompt: System prompt tuple (role, text)
            max_tokens: Maximum tokens allowed in context (default 4000)
            encoding_name: Tiktoken encoding name (default cl100k_base for GPT-3.5/4)

        Returns:
            List of (role, text) tuples ready for LLM
        """
        logger.debug('Building context messages: key=%s, limit=%d, max_tokens=%d', key, limit, max_tokens)
        # Start with system prompt
        context = [system_prompt]

        # Fetch conversation history
        history = self.fetch_conversation_history(key, limit, bot_username)

        if not history:
            logger.debug('No conversation history found for key=%s', key)
            return context

        # Filter out messages with None or empty text
        history = [(role, text) for role, text in history if text]

        if not history:
            logger.debug('No valid messages after filtering for key=%s', key)
            return context

        # Try to get appropriate encoding
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            def count_tokens(text: str) -> int:
                return len(encoding.encode(text))
            logger.debug('Using tiktoken encoding: %s', encoding_name)
        except (KeyError, ValueError, LookupError) as e:
            # If encoding fails, use character count approximation
            # For Russian/Cyrillic text, use more conservative ratio
            logger.warning('Failed to load tiktoken encoding %s: %s, using character approximation', encoding_name, e)
            def count_tokens(text: str) -> int:
                # Roughly 3 chars per token for mixed Latin/Cyrillic
                return max(len(text) // 3, 1)

        # Count system prompt tokens
        system_tokens = count_tokens(system_prompt[1])
        total_tokens = system_tokens

        # Add history messages from most recent backwards, respecting token limit
        included_history = []
        for role, text in reversed(history):
            msg_tokens = count_tokens(text)
            if total_tokens + msg_tokens > max_tokens:
                logger.debug('Token limit reached, stopping at %d messages included', len(included_history))
                break
            included_history.insert(0, (role, text))
            total_tokens += msg_tokens

        context.extend(included_history)
        logger.debug('Context built: total_messages=%d, estimated_tokens=%d', len(context), total_tokens)
        return context
