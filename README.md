# OpenAI Telegram bot responder

Very simple implementation of a private bot that responds to short chat messages. Almost non-existent context awareness

## Using docker-compose

Copy matvey-template to matvey.yml, adjust accordingly, copy example docker-compose template and adjust env vars:

```
cp matvey-template-v2.yml matvey.yml
cp docker-compose-template.yml docker-compose.yml
(edit both files)
docker compose up
```

## quickstart quide

### 0. Install packages

```
pip install openai pyyaml
pip install -U --pre aiogram
```

This project works with python 3.11+.
Also make sure you use aiogram version 3 (~ tested on aiogram==3.3.0)

### 1. Set environmental variables 

| var | example | meaning |
| --- | ------  | ------- |
| `OPENAI_API_KEY` | `'sk-HS1777777777777777777777777777777777777777777771'` | openapi key |
| `TELEGRAM_API_TOKEN` | `'667778888:AAHmHmHmHmHmHmAAAAAAAAAAAHmHmHmHmHm'` | bot token, get one from BotFather |
| `BOT_CONFIG_YAML` | `/etc/matvey.yml` | take matvey-template.yml as example |
| `BOT_CONFIG_TOML` | `/etc/matvey.toml` | take matvey-template.toml as example |

:warning: yaml configuration is derpecated, use toml instead

### 2. Run the actual script

```
python src/bot_handler.py
```

### 3. Add bot to groups, and send messages

First message needs to be tagged. Responses are handled automatically. Messages with length of 1 are discarded

Don't know the group id? Launch the script, add the bot to the chat and issue a `/blerb` command to see chat id info in the logs.
