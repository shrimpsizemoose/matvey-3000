import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, 'src')


class TestRedisStorageInitialization:
    """Test that FSM Redis storage can be initialized with our parameters."""

    def test_redis_storage_accepts_ttl_parameters(self):
        """Verify RedisStorage.from_url accepts state_ttl and data_ttl."""
        from aiogram.fsm.storage.redis import RedisStorage

        # Mock the Redis client creation to avoid actual connection
        with patch('aiogram.fsm.storage.redis.Redis.from_url') as mock_redis:
            mock_redis.return_value = MagicMock()

            # This should not raise TypeError
            storage = RedisStorage.from_url(
                'redis://localhost:6379/0',
                state_ttl=300,
                data_ttl=300,
            )

            assert storage is not None
            assert storage.state_ttl == 300
            assert storage.data_ttl == 300

    def test_redis_storage_accepts_key_builder(self):
        """Verify RedisStorage.from_url accepts key_builder with custom prefix."""
        from aiogram.fsm.storage.redis import RedisStorage
        from aiogram.fsm.storage.base import DefaultKeyBuilder

        with patch('aiogram.fsm.storage.redis.Redis.from_url') as mock_redis:
            mock_redis.return_value = MagicMock()

            key_builder = DefaultKeyBuilder(prefix='mybot:fsm')
            storage = RedisStorage.from_url(
                'redis://localhost:6379/0',
                key_builder=key_builder,
                state_ttl=300,
                data_ttl=300,
            )

            assert storage is not None
            assert storage.key_builder is key_builder

    def test_default_key_builder_generates_prefixed_keys(self):
        """Verify DefaultKeyBuilder generates keys with custom prefix."""
        from aiogram.fsm.storage.base import DefaultKeyBuilder, StorageKey

        key_builder = DefaultKeyBuilder(prefix='mybot:fsm')

        storage_key = StorageKey(
            bot_id=123,
            chat_id=456,
            user_id=789,
        )

        result = key_builder.build(storage_key, 'state')

        assert result.startswith('mybot:fsm:')
        assert '456' in result  # chat_id
        assert '789' in result  # user_id

    def test_redis_storage_rejects_invalid_kwargs(self):
        """Verify that invalid kwargs raise TypeError (regression test)."""
        from aiogram.fsm.storage.redis import RedisStorage

        with patch('aiogram.fsm.storage.redis.Redis.from_url') as mock_redis:
            mock_redis.return_value = MagicMock()

            # key_prefix is not a valid parameter - this should raise
            with pytest.raises(TypeError, match='unexpected keyword argument'):
                RedisStorage.from_url(
                    'redis://localhost:6379/0',
                    key_prefix='invalid:prefix:',
                )
