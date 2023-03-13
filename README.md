# OpenAI Telegram bot responder

Very simple implementation of a private bot that responds to short chat messages. Almost non-existent context awareness

## quickstart quide

### 0. Install packages

```
pip install openai pyyaml aiogram
```

this tested with python3.10, but should work with python3.8 as well

### 1. Set environmental variables 

| var | example | meaning |
| --- | ------  | ------- |
| `OPENAI_API_KEY` | `'sk-HS1777777777777777777777777777777777777777777771'` | openapi key |
| `TELEGRAM_API_TOKEN` | `'667778888:AAHmHmHmHmHmHmAAAAAAAAAAAHmHmHmHmHm'` | bot token, get one from BotFather |
| `BOT_CONFIG_YAML` | `/etc/matvey.yml` | take matvey-template.yml as example |

### 2. Run the actual script

```
python src/bot_handler.py
```

### 3. Add bot to groups, and send messages

First message needs to be tagged. Responses are handled automatically. Messages with length of 1 are discarded

Don't know the group id? Launch the script, add the bot to the chat and issue a `/blerb` command to see chat id info in the logs.
