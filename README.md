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

### 0. Install packages

```
pip install openai anthropic httpx
pip install -U aiogram
```

This project works with python 3.11+.
Also make sure you use aiogram version 3 (~ tested on aiogram==3.4.1)

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

### 3. Add bot to groups, and send messages

First message needs to be tagged. Responses are handled automatically. Messages with length of 1 are discarded

Don't know the group id? Launch the script, add the bot to the chat and issue a `/blerb` command to see chat id info in the logs.

## Using docker-compose

Copy matvey-template.toml to matvey.toml, adjust accordingly, copy example docker-compose template and adjust env vars:

```
cp matvey-template.toml matvey.toml
cp docker-compose-template.yml docker-compose.yml
(edit both files)
docker compose up
```
