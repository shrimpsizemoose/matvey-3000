import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import asdict

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from message_store import MessageStore, StoredChatMessage


@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    redis_mock = MagicMock()
    redis_mock.lrange.return_value = []
    redis_mock.llen.return_value = 0
    redis_mock.rpush.return_value = 1
    redis_mock.delete.return_value = 1
    return redis_mock


@pytest.fixture
def message_store(mock_redis):
    """Create MessageStore with mocked Redis."""
    store = MessageStore.__new__(MessageStore)
    store.redis_conn = mock_redis
    return store


@pytest.fixture
def sample_messages():
    """Create sample chat messages."""
    return [
        StoredChatMessage(
            chat_name="Test Chat",
            from_username="user1",
            from_full_name="User One",
            timestamp=1000,
            text="Hello bot!",
        ),
        StoredChatMessage(
            chat_name="Test Chat",
            from_username="testbot",
            from_full_name="BOT",
            timestamp=1001,
            text="Hello! How can I help?",
        ),
        StoredChatMessage(
            chat_name="Test Chat",
            from_username="user1",
            from_full_name="User One",
            timestamp=1002,
            text="What's the weather?",
        ),
        StoredChatMessage(
            chat_name="Test Chat",
            from_username="testbot",
            from_full_name="BOT",
            timestamp=1003,
            text="I don't have weather data.",
        ),
    ]


class TestStoredChatMessage:
    """Test StoredChatMessage dataclass."""

    def test_serialize_deserialize(self):
        """Test message serialization and deserialization."""
        msg = StoredChatMessage(
            chat_name="Test",
            from_username="user",
            from_full_name="User Name",
            timestamp=12345,
            text="Test message",
        )
        
        serialized = msg.serialize()
        deserialized = StoredChatMessage.deserialize(serialized)
        
        assert deserialized.chat_name == msg.chat_name
        assert deserialized.from_username == msg.from_username
        assert deserialized.from_full_name == msg.from_full_name
        assert deserialized.timestamp == msg.timestamp
        assert deserialized.text == msg.text

    def test_str_representation(self):
        """Test string representation of message."""
        msg = StoredChatMessage(
            chat_name="Test",
            from_username="user",
            from_full_name="User Name",
            timestamp=12345,
            text="Hello",
        )
        
        result = str(msg)
        assert "User Name <user>" in result
        assert "[at 12345]" in result
        assert "Hello" in result


class TestMessageStore:
    """Test MessageStore functionality."""

    def test_save_message(self, message_store, mock_redis, sample_messages):
        """Test saving a message to Redis."""
        msg = sample_messages[0]
        key = "test:key"
        
        message_store.save(key, msg)
        
        mock_redis.rpush.assert_called_once_with(key, msg.serialize())

    def test_save_message_with_cutoff(self, message_store, mock_redis, sample_messages):
        """Test that messages are trimmed when exceeding CUTOFF."""
        msg = sample_messages[0]
        key = "test:key"
        
        # Simulate list length exceeding CUTOFF
        mock_redis.llen.return_value = 2001
        
        message_store.save(key, msg)
        
        mock_redis.ltrim.assert_called_once()

    def test_fetch_messages(self, message_store, mock_redis, sample_messages):
        """Test fetching messages from Redis."""
        key = "test:key"
        serialized = [msg.serialize() for msg in sample_messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.fetch_messages(key, limit=10, raw=False)
        
        assert len(result) == len(sample_messages)
        assert all(isinstance(msg, StoredChatMessage) for msg in result)
        mock_redis.lrange.assert_called_once_with(key, -10, -1)

    def test_fetch_messages_raw(self, message_store, mock_redis, sample_messages):
        """Test fetching raw messages from Redis."""
        key = "test:key"
        serialized = [msg.serialize() for msg in sample_messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.fetch_messages(key, limit=5, raw=True)
        
        assert result == serialized

    def test_fetch_conversation_history(self, message_store, mock_redis, sample_messages):
        """Test fetching conversation history as (role, text) tuples."""
        key = "test:key"
        bot_username = "testbot"
        serialized = [msg.serialize() for msg in sample_messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.fetch_conversation_history(key, limit=10, bot_username=bot_username)
        
        expected = [
            ('user', 'Hello bot!'),
            ('assistant', 'Hello! How can I help?'),
            ('user', "What's the weather?"),
            ('assistant', "I don't have weather data."),
        ]
        assert result == expected

    def test_clear_conversation_history(self, message_store, mock_redis):
        """Test clearing conversation history."""
        key = "test:key"
        mock_redis.llen.return_value = 42
        
        deleted_count = message_store.clear_conversation_history(key)
        
        assert deleted_count == 42
        mock_redis.delete.assert_called_once_with(key)

    def test_build_context_messages_empty_history(self, message_store, mock_redis):
        """Test building context with no history."""
        key = "test:key"
        system_prompt = ('system', 'You are a helpful bot')
        mock_redis.lrange.return_value = []
        
        result = message_store.build_context_messages(
            key=key,
            limit=10,
            bot_username="testbot",
            system_prompt=system_prompt,
            max_tokens=4000,
        )
        
        assert result == [system_prompt]

    def test_build_context_messages_with_history(self, message_store, mock_redis, sample_messages):
        """Test building context with conversation history."""
        key = "test:key"
        system_prompt = ('system', 'You are a helpful bot')
        bot_username = "testbot"
        serialized = [msg.serialize() for msg in sample_messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.build_context_messages(
            key=key,
            limit=10,
            bot_username=bot_username,
            system_prompt=system_prompt,
            max_tokens=4000,
        )
        
        # Should include system prompt + all messages
        assert len(result) >= 1
        assert result[0] == system_prompt
        # Check that history is included
        assert any(text == 'Hello bot!' for role, text in result)

    def test_build_context_messages_filters_none_text(self, message_store, mock_redis):
        """Test that messages with None or empty text are filtered out."""
        key = "test:key"
        system_prompt = ('system', 'You are a helpful bot')
        
        # Create messages with None and empty text
        messages = [
            StoredChatMessage("Chat", "user1", "User", 1000, "Valid message"),
            StoredChatMessage("Chat", "user1", "User", 1001, None),
            StoredChatMessage("Chat", "user1", "User", 1002, ""),
            StoredChatMessage("Chat", "user1", "User", 1003, "Another valid"),
        ]
        serialized = [msg.serialize() for msg in messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.build_context_messages(
            key=key,
            limit=10,
            bot_username="testbot",
            system_prompt=system_prompt,
            max_tokens=4000,
        )
        
        # Should only include system prompt + 2 valid messages
        assert len(result) == 3
        assert result[0] == system_prompt
        assert ('user', 'Valid message') in result
        assert ('user', 'Another valid') in result

    def test_build_context_messages_respects_token_limit(self, message_store, mock_redis):
        """Test that context building respects token limits."""
        key = "test:key"
        system_prompt = ('system', 'You are a helpful bot')
        
        # Create messages with long text
        long_text = "word " * 1000  # Very long message
        messages = [
            StoredChatMessage("Chat", "user1", "User", 1000, long_text),
            StoredChatMessage("Chat", "user1", "User", 1001, long_text),
            StoredChatMessage("Chat", "user1", "User", 1002, "Short message"),
        ]
        serialized = [msg.serialize() for msg in messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.build_context_messages(
            key=key,
            limit=10,
            bot_username="testbot",
            system_prompt=system_prompt,
            max_tokens=100,  # Very low token limit
        )
        
        # Should include system prompt and maybe one short message
        # but not all the long messages
        assert len(result) <= 3
        assert result[0] == system_prompt

    def test_build_context_messages_prioritizes_recent(self, message_store, mock_redis):
        """Test that most recent messages are prioritized when token limit is reached."""
        key = "test:key"
        system_prompt = ('system', 'Short prompt')
        
        # Create messages - most recent should be prioritized
        messages = [
            StoredChatMessage("Chat", "user1", "User", 1000, "Old message"),
            StoredChatMessage("Chat", "user1", "User", 1001, "Middle message"),
            StoredChatMessage("Chat", "user1", "User", 1002, "Recent message"),
        ]
        serialized = [msg.serialize() for msg in messages]
        mock_redis.lrange.return_value = serialized
        
        result = message_store.build_context_messages(
            key=key,
            limit=10,
            bot_username="testbot",
            system_prompt=system_prompt,
            max_tokens=50,  # Limited tokens
        )
        
        # Most recent message should be included
        texts = [text for role, text in result]
        if len(result) > 1:  # If any history was included
            assert "Recent message" in texts

    def test_fetch_stats(self, message_store, mock_redis):
        """Test fetching statistics about stored messages."""
        pattern = "test:*"
        mock_redis.keys.return_value = [b"test:chat1", b"test:chat2"]
        mock_redis.type.return_value = b"list"
        mock_redis.llen.side_effect = [10, 20]
        
        result = message_store.fetch_stats(pattern)
        
        assert len(result) == 2
        assert ("test:chat1", 10) in result
        assert ("test:chat2", 20) in result
