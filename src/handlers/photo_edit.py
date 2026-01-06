import logging

from aiogram import Router, types
from aiogram.filters import Command, CommandObject

from bot import config, get_replied_photo_bytes, react
from providers import ReplicateEdit

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["edit"]),
)
async def handle_edit_command(message: types.Message, command: CommandObject) -> None:
    logger.info("Command /edit: chat_id=%s, user=%s", message.chat.id, message.from_user.username)

    image_bytes = await get_replied_photo_bytes(message)
    if not image_bytes:
        await message.reply(
            "Reply to a photo with this command.\n"
            "Example: <code>/edit make it look like a watercolor painting</code>"
        )
        await react(success=False, message=message)
        return

    instruction = command.args
    if not instruction:
        await message.reply("Provide an instruction.\nExample: <code>/edit add sunglasses</code>")
        await react(success=False, message=message)
        return

    await message.chat.do("upload_photo")
    progress_msg = await message.answer("Editing with Replicate...")

    result = await ReplicateEdit.edit(image_bytes, instruction)

    await progress_msg.delete()
    if result.success:
        await message.answer_photo(types.URLInputFile(result.image_url), caption=f"Edit: {instruction}")
        await react(success=True, message=message)
    else:
        await message.answer(f"Edit failed: {result.error}")
        await react(success=False, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["remove"]),
)
async def handle_remove_command(message: types.Message, command: CommandObject) -> None:
    logger.info("Command /remove: chat_id=%s, user=%s", message.chat.id, message.from_user.username)

    image_bytes = await get_replied_photo_bytes(message)
    if not image_bytes:
        await message.reply(
            "Reply to a photo with this command.\n"
            "Example: <code>/remove the person in background</code>"
        )
        await react(success=False, message=message)
        return

    target = command.args
    if not target:
        await message.reply("What should I remove?\nExample: <code>/remove the watermark</code>")
        await react(success=False, message=message)
        return

    await message.chat.do("upload_photo")
    progress_msg = await message.answer("Removing object...")

    result = await ReplicateEdit.remove_object(image_bytes, target)

    await progress_msg.delete()
    if result.success:
        await message.answer_photo(types.URLInputFile(result.image_url), caption=f"Removed: {target}")
        await react(success=True, message=message)
    else:
        await message.answer(f"Remove failed: {result.error}")
        await react(success=False, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["replace"]),
)
async def handle_replace_command(message: types.Message, command: CommandObject) -> None:
    logger.info("Command /replace: chat_id=%s, user=%s", message.chat.id, message.from_user.username)

    image_bytes = await get_replied_photo_bytes(message)
    if not image_bytes:
        await message.reply(
            "Reply to a photo with this command.\n"
            "Example: <code>/replace the car -> a red sports car</code>"
        )
        await react(success=False, message=message)
        return

    args = command.args or ""
    # Parse "old -> new" or "old → new" format
    for separator in [" -> ", " → ", "->", "→"]:
        if separator in args:
            parts = args.split(separator, 1)
            target, replacement = parts[0].strip(), parts[1].strip()
            break
    else:
        await message.reply(
            "Use format: <code>/replace old -> new</code>\n"
            "Example: <code>/replace the sky -> a sunset sky</code>"
        )
        await react(success=False, message=message)
        return

    if not target or not replacement:
        await message.reply("Both target and replacement are required.")
        await react(success=False, message=message)
        return

    await message.chat.do("upload_photo")
    progress_msg = await message.answer(f"Replacing {target}...")

    result = await ReplicateEdit.replace_object(image_bytes, target, replacement)

    await progress_msg.delete()
    if result.success:
        await message.answer_photo(
            types.URLInputFile(result.image_url),
            caption=f"Replaced: {target} → {replacement}",
        )
        await react(success=True, message=message)
    else:
        await message.answer(f"Replace failed: {result.error}")
        await react(success=False, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["remove_bg"]),
)
async def handle_remove_bg_command(message: types.Message) -> None:
    logger.info("Command /remove_bg: chat_id=%s, user=%s", message.chat.id, message.from_user.username)

    image_bytes = await get_replied_photo_bytes(message)
    if not image_bytes:
        await message.reply("Reply to a photo with this command.")
        await react(success=False, message=message)
        return

    await message.chat.do("upload_photo")
    progress_msg = await message.answer("Removing background...")

    result = await ReplicateEdit.remove_background(image_bytes)

    await progress_msg.delete()
    if result.success:
        await message.answer_photo(types.URLInputFile(result.image_url), caption="Background removed")
        await react(success=True, message=message)
    else:
        await message.answer(f"Remove background failed: {result.error}")
        await react(success=False, message=message)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["background", "bg"]),
)
async def handle_background_command(message: types.Message, command: CommandObject) -> None:
    logger.info("Command /background: chat_id=%s, user=%s", message.chat.id, message.from_user.username)

    image_bytes = await get_replied_photo_bytes(message)
    if not image_bytes:
        await message.reply(
            "Reply to a photo with this command.\n"
            "Example: <code>/bg sunset beach</code>"
        )
        await react(success=False, message=message)
        return

    new_bg = command.args
    if not new_bg:
        await message.reply(
            "Describe the new background.\n"
            "Example: <code>/bg a cozy coffee shop</code>\n"
            "To just remove background, use <code>/remove_bg</code>"
        )
        await react(success=False, message=message)
        return

    await message.chat.do("upload_photo")
    progress_msg = await message.answer("Replacing background...")

    result = await ReplicateEdit.replace_background(image_bytes, new_bg)

    await progress_msg.delete()
    if result.success:
        await message.answer_photo(types.URLInputFile(result.image_url), caption=f"Background: {new_bg}")
        await react(success=True, message=message)
    else:
        await message.answer(f"Background replace failed: {result.error}")
        await react(success=False, message=message)
