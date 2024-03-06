import os
import sys
import tempfile

from config import Config
from message_store import MessageStore


def main(config: Config, store: MessageStore, chat_id: int, limit: int = -1):
    tag = f'matvey-3000:history:{config.me_strip_lower}:{chat_id}'

    fp, fname = tempfile.mkstemp(prefix='matvey-3000')
    for m in store.fetch_messages(key=tag, raw=True):
        print(m.decode(), file=fp)
    fp.close()

    print(f'Saved contents of {tag} as {fname}')


if __name__ == '__main__':
    if len(sys.arvg) != 2:
        print('Need chat_id as a parameter')
        sys.exit(1)
    chat_id = int(sys.argv[1])
    config = Config.read_toml(path=os.getenv('BOT_CONFIG_TOML'))
    store = MessageStore.from_env()
    main(config, store, chat_id)
