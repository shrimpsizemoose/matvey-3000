from aiogram import Dispatcher

from . import admin, images, photo_edit, summary, text, voice


def include_all_routers(dp: Dispatcher) -> None:
    """Include all handler routers in the dispatcher."""
    dp.include_router(admin.router)
    dp.include_router(images.router)
    dp.include_router(photo_edit.router)
    dp.include_router(voice.router)
    dp.include_router(summary.router)
    dp.include_router(text.router)  # Must be last (catches all text messages)
