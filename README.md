# OpenAI Telegram bot responder

Very simple implementation of a private bot that responds to short chat messages. Almost non-existent context awareness

## Using docker-compose

Copy matvey-template.toml to matvey.toml, adjust accordingly, copy example docker-compose template and adjust env vars:

```
cp matvey-template-v2.toml matvey.toml
cp docker-compose-template.yml docker-compose.yml
(edit both files)
docker compose up
```

## quickstart quide

### 0. Install uv and dependencies

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

Install uv (if not already installed):
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install dependencies:
```
uv sync
```

This project works with python 3.11+.

### 1. Set environmental variables

| var | example | meaning |
| --- | ------  | ------- |
| `OPENAI_API_KEY` | `'sk-HS1777777777777777777777777771'` | openapi key |
| `ANTHROPIC_API_KEY` | `sk-ant-api03-99-jp...Q-6...A..A'` | anthropic_key |
| `TELEGRAM_API_TOKEN` | `'667778888:AAHmHmAAAAAAAHmHmHm'` | bot token |
| `YANDEXGPT_FOLDER_ID` | `b1g7oooooooooooooooo` | yandex service folder id |
| `YANDEXGPT_API_KEY` | `AQiiii..........iiiiii-rzO` | yandex gpt api key |
| `KANDINSKI_API_KEY` | `CD53.................0F49F` | kandinski api key |
| `KANDINSKI_API_SECRET` | `4A470B............98942` | kandinski api secret |
| `REPLICATE_API_TOKEN` | `r8_xxxxxxxxxx` | Replicate API token for photo editing |
| `BOT_CONFIG_TOML` | `/etc/matvey.toml` | take matvey-template.toml as example |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for message history and FSM state |
| `FSM_REDIS_PREFIX` | `fsm:mybot` | optional prefix for FSM keys (default: `fsm:<bot_username>`) |

Set up only the ones that you are going to use
See [.envrc_template](./.envrc_template) for example [diren](https://direnv.net/) config

### 2. Run the script

```
make run
```

Or directly with uv:
```
uv run python src/bot_handler.py
```

### 3. Add bot to groups, and send messages

First message needs to be tagged. Responses are handled automatically. Messages with length of 1 are discarded

Don't know the group id? Launch the script, add the bot to the chat and issue a `/blerb` command to see chat id info in the logs.

## Commands

| Command | Description |
| ------- | ----------- |
| `/pic <prompt>` | Generate image with DALL-E 2 |
| `/pic3 <prompt>` | Generate image with DALL-E 3 |
| `/pik <prompt>` | Generate image with Kandinski |
| `/edit <instruction>` | Edit photo with natural language (reply to photo) |
| `/remove <object>` | Remove object from photo (reply to photo) |
| `/replace <old> -> <new>` | Replace object in photo (reply to photo) |
| `/remove_bg` | Remove background from photo (reply to photo) |
| `/background <description>` | Replace background (reply to photo) |
| `/reimagine <modification>` | Reimagine attached photo with GPT-4 Vision + DALL-E 3 |
| `/tts [voice:] <text>` | Convert text to speech (requires `voice_enabled`) |
| `/ru <text>` | Translate to Russian |
| `/en <text>` | Translate to English |
| `/mode_claude` | Switch to Anthropic Claude |
| `/mode_chatgpt` | Switch to OpenAI ChatGPT |
| `/mode_yandex` | Switch to YandexGPT |
| `/prompt [new_prompt]` | Show or set system prompt |
| `/new_chat` | Clear conversation history |
| `/blerb` | Show chat ID |

Voice messages and video notes are automatically transcribed when `voice_enabled` is set.

## Per-chat configuration

In your TOML config, each chat can have these options:

```toml
[[chats.allowed]]
id = 123456789
who = "user or group name"
provider = "openai"           # openai, anthropic, or yandexgpt
save_messages = true          # persist messages to Redis
context_enabled = true        # use conversation history
max_context_messages = 10     # how many messages to include
summary_enabled = false       # enable /sammari command
voice_enabled = false         # enable voice transcription and /tts
tts_voice = "alloy"           # default TTS voice (alloy, echo, fable, onyx, nova, shimmer)
disabled_commands = ["/pik"]  # disable specific commands
```

## Development

Run tests:
```
make @test
```

Or directly:
```
uv run pytest -s -vv tests/
```

Update dependencies:
```
make lock
```
