import pytest
import sys
from pathlib import Path
import textwrap
import warnings

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config import Config


@pytest.fixture()
def user1_id():
    return 12345678


@pytest.fixture()
def user2_id():
    return 87654321


@pytest.fixture()
def bot_me():
    return '@dummy_bot'


@pytest.fixture()
def default_prompt():
    return 'You are a bot named Matvey. This is default prompt'


@pytest.fixture()
def new_nondefault_prompt():
    return 'New nondefault prompt'


@pytest.fixture()
def tmp_path_toml_config_v4(tmp_path, bot_me, user1_id, user2_id, default_prompt):
    toml_content = f'''
    me = "{bot_me}"
    version = 4
    positive_emojis = "👍🔥🥰🎉🤩"
    negative_emojis = "👎🤔🤯🤬💔"

    [models]
    chatgpt = "gpt-3.5-turbo-1106"
    anthropic = "claude-2"
    yandexgpt = "yandexgpt-lite"

    [defaults]
    provider = "yandexgpt"
    prompt = """
    {default_prompt}
    """

    [translations]
    en_to_ru = """
    You are a bot that just translates all messages from English to Russian.
    For example, when I write:
      To h'll wit it
    You respond:
      EN: To hell with it
      RU: К чёрту это

      Подобное выражение означает фрустрацию и усталость происходящим.
      Аккуратно, выражение немного вульгарно
    """
    ru_to_en = """
    You are a bot that just translates all messages from Russian to English.
    For example, when I write:
      Ля какя цаца
    You respond:
      RU: Ля какая цаца
      EN: Wow, what a sight!
      EN: Wow, what a thing!

      This phrase can be used to express surprise at something attractive
    """

    [[chats.allowed]]
    id = {user1_id}
    who = "user1"
    prompt = """
    custom prompt for chat_id={user1_id}
    this chat wants different prompt
    """

    [[chats.allowed]]
    id = {user2_id}
    who = "user2"
    '''
    toml_content = textwrap.dedent(toml_content)
    toml_file = tmp_path / 'test_config_v4.toml'
    toml_file.write_text(toml_content)
    return toml_file


def test_toml_config_parsing_default_config_parses_bot_me(
    bot_me, tmp_path_toml_config_v4
):
    with warnings.catch_warnings():
        config = Config.read_toml(tmp_path_toml_config_v4)

    assert config.me == bot_me


def test_config_can_override_prompt_for_user1_no_effect_on_user2(
    bot_me,
    tmp_path_toml_config_v4,
    user1_id,
    user2_id,
    default_prompt,
    new_nondefault_prompt,
):
    with warnings.catch_warnings():
        config = Config.read_toml(tmp_path_toml_config_v4)

    prompt_u2 = config[user2_id].prompt
    assert prompt_u2 == default_prompt

    prompt_u1 = config[user1_id].prompt
    assert prompt_u1 != default_prompt
    config.override_prompt_for_chat(user1_id, new_nondefault_prompt)

    new_prompt_u1 = config[user1_id].prompt
    assert new_prompt_u1 == new_nondefault_prompt

    # changing prompt for one user cannot override prompt for another one
    new_prompt2 = config[user2_id].prompt
    assert prompt_u2 == new_prompt2
