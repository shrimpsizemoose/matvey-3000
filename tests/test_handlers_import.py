import os
import sys
from pathlib import Path

# Set dummy env vars before importing handlers (bot.py creates Bot at import time)
os.environ.setdefault('TELEGRAM_API_TOKEN', '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')
os.environ.setdefault('BOT_CONFIG_TOML', str(Path(__file__).parent.parent / 'matvey-template.toml'))
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def test_handlers_import():
    """Smoke test to ensure all handlers can be imported without errors."""
    from handlers import admin, images, photo_edit, summary, text, voice

    assert admin.router is not None
    assert images.router is not None
    assert photo_edit.router is not None
    assert summary.router is not None
    assert text.router is not None
    assert voice.router is not None
