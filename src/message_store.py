from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

import redis


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
        logger.info('Redis message store connected')

    @classmethod
    def from_env(cls) -> MessageStore:
        url = os.getenv('REDIS_URL')
        return cls(url)

    def save(self, tag: str, message: StoredChatMessage):
        # might need to have a deeper per-hour or per-day split
        self.redis_conn.rpush(tag, message.serialize())
        if self.redis_conn.llen(tag) > CUTOFF:
            self.redis_conn.ltrim(tag, 0, CUTOFF)

    def fetch_stats(self, keys_pattern: str) -> list[tuple[str, int]]:
        keys = self.redis_conn.keys(keys_pattern)
        return [
            (key.decode(), self.redis_conn.llen(key))
            for key in keys
            if self.redis_conn.type(key) == b'list'  # noqa
        ]

    def fetch_messages(
        self, key: str, limit: int, raw: bool = False
    ) -> list[StoredChatMessage] | list[bytes]:
        messages = self.redis_conn.lrange(key, -limit, -1)
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
        messages = self.fetch_messages(key=key, limit=limit, raw=False)
        conversation = []
        
        for msg in messages:
            # Determine role based on username
            role = 'assistant' if msg.from_username == bot_username else 'user'
            conversation.append((role, msg.text))
        
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
        return count

    def build_context_messages(
        self,
        key: str,
        limit: int,
        bot_username: str,
        system_prompt: tuple[str, str],
        max_tokens: int = 4000,
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
            
        Returns:
            List of (role, text) tuples ready for LLM
        """
        import tiktoken
        
        # Start with system prompt
        context = [system_prompt]
        
        # Fetch conversation history
        history = self.fetch_conversation_history(key, limit, bot_username)
        
        if not history:
            return context
        
        # Try to estimate tokens (using cl100k_base as default encoding)
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # If tiktoken fails, just use character count approximation
            # Roughly 4 characters per token
            def count_tokens(text: str) -> int:
                return len(text) // 4
        else:
            def count_tokens(text: str) -> int:
                return len(encoding.encode(text))
        
        # Count system prompt tokens
        system_tokens = count_tokens(system_prompt[1])
        total_tokens = system_tokens
        
        # Add history messages from most recent backwards, respecting token limit
        included_history = []
        for role, text in reversed(history):
            msg_tokens = count_tokens(text)
            if total_tokens + msg_tokens > max_tokens:
                break
            included_history.insert(0, (role, text))
            total_tokens += msg_tokens
        
        context.extend(included_history)
        return context

