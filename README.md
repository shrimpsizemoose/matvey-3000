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
| `BOT_CONFIG_TOML` | `/etc/matvey.toml` | take matvey-template.toml as example |

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
