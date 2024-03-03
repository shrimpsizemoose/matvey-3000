from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

import redis


logger = logging.getLogger(__name__)


@dataclass
class StoredChatMessage:
    username: str
    full_name: str
    text: str

    def serialize(self):
        return json.dumps(asdict(self), ensure_ascii=False)


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

    def fetch_stats(self, keys_pattern: str) -> list[tuple[str, int]]:
        keys = self.redis_conn.keys(keys_pattern)
        return [
            (key.decode(), self.redis_conn.llen(key))
            for key in keys
            if self.redis_conn.type(key) == b'list'  # noqa
        ]
