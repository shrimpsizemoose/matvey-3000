import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from aiogram import types
from bot_handler import extract_message_chain


@pytest.fixture()
def user1_id():
    return 12345678


@pytest.fixture()
def bot_id():
    return 22222222


@pytest.fixture()
def mock_solo_message(user1_id, mocker):
    msg = mocker.Mock(spec=types.Message)
    msg.text = 'solo message'
    msg.reply_to_message = None
    msg.from_user = mocker.Mock(spec=types.User)
    msg.from_user.id = user1_id
    return msg


@pytest.fixture()
def mock_thread(user1_id, bot_id, mocker):
    """
    user writes a few messages, tags bot, then communicates with a bot a bit

    U1 (new message): first message
    U2 (reply to U1): second message
    U3 (reply to U2): third message. tag bot here @tag_bot
    A1 (reply to U3): fourth message. (1st response from assistant)
    U4 (reply to A1): fifth message
    A2 (reply to U4): sixth message. (2nd response from assistant)
    U5 (reply to A2): FINAL seventh message. The one that we recieved

    """
    u1 = mocker.Mock(spec=types.Message)
    u1.text = 'first message'
    u1.reply_to_message = None
    u1.from_user = mocker.Mock(spec=types.User)
    u1.from_user.id = user1_id

    u2 = mocker.Mock(spec=types.Message)
    u2.text = 'second message'
    u2.reply_to_message = u1
    u2.from_user = mocker.Mock(spec=types.User)
    u2.from_user.id = user1_id

    u3 = mocker.Mock(spec=types.Message)
    u3.text = 'third message. tag bot here @tag_bot'
    u3.reply_to_message = u2
    u3.from_user = mocker.Mock(spec=types.User)
    u3.from_user.id = user1_id

    a1 = mocker.Mock(spec=types.Message)
    a1.text = 'fourth message. (1st response from assistant)'
    a1.reply_to_message = u3
    a1.from_user = mocker.Mock(spec=types.User)
    a1.from_user.id = bot_id

    u4 = mocker.Mock(spec=types.Message)
    u4.text = 'fifth message'
    u4.reply_to_message = a1
    u4.from_user = mocker.Mock(spec=types.User)
    u4.from_user.id = user1_id

    a2 = mocker.Mock(spec=types.Message)
    a2.text = 'sixth message. (2nd response from assistant)'
    a2.reply_to_message = u4
    a2.from_user = mocker.Mock(spec=types.User)
    a2.from_user.id = bot_id

    u5 = mocker.Mock(spec=types.Message)
    u5.text = 'FINAL seventh message. The one that we recieved'
    u5.reply_to_message = a2
    u5.from_user = mocker.Mock(spec=types.User)
    u5.from_user.id = user1_id

    return [u1, u2, u3, a1, u4, a2, u5]


@pytest.fixture()
def mock_last_thread_message(mock_thread):
    return mock_thread[-1]


@pytest.fixture()
def mock_chain_expected(bot_id, user1_id, mock_thread):
    chain = []
    for msg in mock_thread:
        text = msg.text
        role = ''
        if msg.from_user.id == bot_id:
            role = 'assistant'
        elif msg.from_user.id == user1_id:
            role = 'user'
        chain.append((role, text))
    return chain


def test_extract_message_chain_solo(bot_id, mock_solo_message):
    got_chain = extract_message_chain(mock_solo_message, bot_id)

    assert got_chain == [('user', mock_solo_message.text)]


def test_extract_message_chain_thread(
    bot_id, mock_last_thread_message, mock_chain_expected
):
    got_chain = extract_message_chain(mock_last_thread_message, bot_id)

    assert len(got_chain) == len(mock_chain_expected)
    assert got_chain == mock_chain_expected
