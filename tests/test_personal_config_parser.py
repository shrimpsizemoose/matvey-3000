import pytest
import yaml
import textwrap
import warnings

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
def tmp_path_yaml_config_no_version(
    tmp_path, bot_me, user1_id, user2_id, default_prompt
):
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
def tmp_path_yaml_config_version_2(
    tmp_path, bot_me, user1_id, user2_id, default_prompt
):
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


@pytest.fixture()
def tmp_path_toml_config_version_4(
    tmp_path, bot_me, user1_id, user2_id, default_prompt
):
    toml_content = f'''
    me = "{bot_me}"
    version = 4
    model_chatgpt = "gpt-3.5-turbo"
    model_anthropic = "claude-2"
    model_yandexgpt = "yandexgpt-lite"

    [setup]
    providers.default = "openai"
    default_prompt = """
    {default_prompt}
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


def test_yaml_config_parsing_default_config_parses_bot_me(
    bot_me, tmp_path_yaml_config_no_version, user2_id, default_prompt
):
    with warnings.catch_warnings():
        config = Config.read_yaml(tmp_path_yaml_config_no_version)

    assert config.me == bot_me


def test_config_parsing_no_version_warns_and_gives_version_1(
    tmp_path_yaml_config_no_version, user1_id, user2_id, default_prompt
):
    with warnings.catch_warnings(record=True) as w:
        config = Config.read_yaml(tmp_path_yaml_config_no_version)
        assert len(w) == 2
        assert all(issubclass(ww.category, DeprecationWarning) for ww in w)
        assert any("version" in str(ww.message) for ww in w)
        assert any("yaml" in str(ww.message) for ww in w)

    assert config.version == Config.VERSION_ONE


def test_config_parsing_no_version_gives_default_prompt(
    tmp_path_yaml_config_no_version, user1_id, user2_id, default_prompt
):
    with warnings.catch_warnings():
        config = Config.read_yaml(tmp_path_yaml_config_no_version)

    for uid in (user1_id, user2_id):
        _, prompt = config.prompt_message_for_user(uid)
        assert prompt == default_prompt


def test_config_parsing_version_2_yaml_deprecation_warning(
    tmp_path_yaml_config_version_2, user1_id, user2_id, default_prompt
):
    with warnings.catch_warnings(record=True) as w:
        config = Config.read_yaml(tmp_path_yaml_config_version_2)
        assert len(w) == 1
        assert all(issubclass(ww.category, DeprecationWarning) for ww in w)
        assert any("yaml" in str(ww.message) for ww in w)

    assert config.version == Config.VERSION_TWO


def test_yaml_config_parsing_version_2_when_u2_gets_default_prompt(
    bot_me, tmp_path_yaml_config_version_2, user2_id, default_prompt
):
    with warnings.catch_warnings():
        config = Config.read_yaml(tmp_path_yaml_config_version_2)

    assert config.me == bot_me
    assert config.version == Config.VERSION_TWO

    _, prompt2 = config.prompt_message_for_user(user2_id)
    assert prompt2 == default_prompt


def test_yaml_config_can_override_prompt_for_user1_no_effect_on_user2(
    bot_me,
    tmp_path_yaml_config_version_2,
    user1_id,
    user2_id,
    default_prompt,
    new_nondefault_prompt,
):
    with warnings.catch_warnings():
        config = Config.read_yaml(tmp_path_yaml_config_version_2)

    _, prompt2 = config.prompt_message_for_user(user2_id)
    assert prompt2 == default_prompt

    _, prompt1 = config.prompt_message_for_user(user1_id)
    assert prompt1 != default_prompt
    config.override_prompt_for_chat(user1_id, new_nondefault_prompt)

    _, new_prompt1 = config.prompt_message_for_user(user1_id)
    assert new_prompt1 == new_nondefault_prompt

    # changing prompt for one user cannot override prompt for another one
    _, new_prompt2 = config.prompt_message_for_user(user2_id)
    assert prompt2 == new_prompt2


def test_toml_config_parsing_parses_bot_me(
    bot_me, tmp_path_toml_config_version_4, user2_id, default_prompt
):
    with warnings.catch_warnings():
        config = Config.read_toml(tmp_path_toml_config_version_4)

    assert config.me == bot_me
