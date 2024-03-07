import os
import sys
import tempfile

from config import Config
from message_store import MessageStore


def main(config: Config, store: MessageStore, chat_id: int, limit: int = -1):
    tag = f'matvey-3000:history:{config.me_strip_lower}:{chat_id}'
    tag = f'matvey-3000:history:matthew_3000_bot:{chat_id}'

    with tempfile.NamedTemporaryFile(
        mode='w+t',
        prefix='matvey-3000',
        delete=False,
    ) as fp:
        messages = store.fetch_messages(key=tag, limit=-1, raw=True)
        print(f'Found {len(messages)} messages in {tag}')
        for m in messages:
            print(m.decode().strip(), file=fp)
        print(f'Saved contents as {fp.name}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Need chat_id as a parameter')
        sys.exit(1)
    chat_id = int(sys.argv[1])
    config = Config.read_toml(path=os.getenv('BOT_CONFIG_TOML'))
    store = MessageStore.from_env()
    main(config, store, chat_id)
