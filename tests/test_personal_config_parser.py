import pytest
import yaml
import textwrap

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
    return 'Now nondefault prompt'


@pytest.fixture()
def tmp_path_no_version(tmp_path, bot_me, user1_id, user2_id, default_prompt):
    yaml_content = f"""
    ---
    me: "{bot_me}"
    model: "gpt-3.5-turbo"
    setup:
      - role: system
        content: {default_prompt}
    allowed_chat_id:
      - {user1_id}
      - {user2_id}
    """
    yaml_content = textwrap.dedent(yaml_content)
    yaml_file = tmp_path / 'test_config_v1.yaml'
    yaml_file.write_text(yaml_content)
    return yaml_file


@pytest.fixture()
def tmp_path_explicit_version_2(tmp_path, bot_me, user1_id, user2_id, default_prompt):
    yaml_content = f"""
    ---
    me: "{bot_me}"
    model: "gpt-3.5-turbo"
    version: 2
    setup:
      default_prompt: {default_prompt}
      prompts:
        {user1_id}: |
          prompt for chat_id of {user1_id}
          this chat wants different prompt
    allowed_chat_id:
      - {user1_id}
      - {user2_id}
    """
    yaml_content = textwrap.dedent(yaml_content)
    yaml_file = tmp_path / 'test_config_v2.yaml'
    yaml_file.write_text(yaml_content)
    return yaml_file


def test_config_parsing_no_version_means_version_1(bot_me, tmp_path_no_version, user1_id, user2_id, default_prompt):
    config = Config.read_yaml(tmp_path_no_version)
    assert config.me == bot_me
    assert config.version == Config.VERSION_ONE

    assert config.prompt_message_for_user(user1_id)['content'] == default_prompt
    assert config.prompt_message_for_user(user2_id)['content'] == default_prompt


def test_config_parsing_version_2(bot_me, tmp_path_explicit_version_2, user1_id, user2_id, default_prompt):
    config = Config.read_yaml(tmp_path_explicit_version_2)
    assert config.me == bot_me
    assert config.version == Config.VERSION_TWO

    assert config.prompt_message_for_user(user1_id)['content'] != default_prompt
    assert config.prompt_message_for_user(user2_id)['content'] == default_prompt


def test_config_can_override_prompt(bot_me, tmp_path_explicit_version_2, user1_id, user2_id, default_prompt, new_nondefault_prompt):
    config = Config.read_yaml(tmp_path_explicit_version_2)
    assert config.me == bot_me
    assert config.version == Config.VERSION_TWO

    assert config.prompt_message_for_user(user1_id)['content'] != default_prompt
    config.override_prompt_for_chat(user1_id, new_nondefault_prompt)
    assert config.prompt_message_for_user(user1_id)['content'] == new_nondefault_prompt
    assert config.prompt_message_for_user(user2_id)['content'] == default_prompt
