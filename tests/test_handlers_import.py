import sys
from pathlib import Path

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
