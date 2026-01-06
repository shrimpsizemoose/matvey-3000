import base64
import logging
import time as time_module

import openai
from aiogram import F, Router, types
from aiogram.filters import Command

from bot import bot, config, react
import metrics
from providers import ImageResponse, TextResponse

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=["pic"]),
)
async def gimme_pic(message: types.Message, command: types.CommandObject):
    logger.info(
        "Command /pic received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    start_time = time_module.perf_counter()
    prompt = command.args
    logger.debug("DALL-E image generation requested, prompt=%r", prompt)
    await message.chat.do("upload_photo")
    try:
        response = await ImageResponse.generate(prompt, mode="dall-e")
    except openai.BadRequestError as e:
        logger.warning(
            "DALL-E generation failed for chat_id=%s, prompt=%r, error=%s",
            message.chat.id,
            prompt,
            e,
        )
        metrics.requests_total.labels(command='pic', status='error').inc()
        metrics.errors_total.labels(error_type='bad_request').inc()
        messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
        messages_to_send.append(
            (
                "user",
                f'объясни трагикомичной шуткой почему OpenAI не может сгенерировать картинку по запросу "{prompt}"',
            )
        )
        await message.chat.do("typing")
        llm_reply = await TextResponse.generate(
            config=config,
            chat_id=message.chat.id,
            messages=messages_to_send,
        )
        await message.answer(llm_reply.text)
        await react(success=False, message=message)
    else:
        logger.info(
            "DALL-E image generated successfully for chat_id=%s", message.chat.id
        )
        metrics.requests_total.labels(command='pic', status='success').inc()
        metrics.images_generated.labels(model='dall-e-2').inc()
        await message.chat.do("upload_photo")
        image_from_url = types.URLInputFile(response.b64_or_url)
        caption = f"DALL-E 2 prompt: {prompt}"
        await message.answer_photo(image_from_url, caption=caption)
        await react(success=True, message=message)
    finally:
        metrics.request_duration.labels(command='pic').observe(time_module.perf_counter() - start_time)


@router.message(
    config.filter_command_not_disabled_for_chat,
    config.filter_chat_allowed,
    Command(commands=["pic3"]),
)
async def gimme_pic3(message: types.Message, command: types.CommandObject):
    logger.info(
        "Command /pic3 received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    start_time = time_module.perf_counter()
    prompt = command.args
    logger.debug("DALL-E 3 image generation requested, prompt=%r", prompt)
    await message.chat.do("upload_photo")
    try:
        response = await ImageResponse.generate(prompt, mode="dall-e-3")
    except openai.BadRequestError as e:
        logger.warning(
            "DALL-E 3 generation failed for chat_id=%s, prompt=%r, error=%s",
            message.chat.id,
            prompt,
            e,
        )
        metrics.requests_total.labels(command='pic3', status='error').inc()
        metrics.errors_total.labels(error_type='bad_request').inc()
        messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
        messages_to_send.append(
            (
                "user",
                f'объясни трагикомичной шуткой почему OpenAI не может сгенерировать картинку по запросу "{prompt}"',  # noqa
            )
        )
        await message.chat.do("typing")
        llm_reply = await TextResponse.generate(
            config=config,
            chat_id=message.chat.id,
            messages=messages_to_send,
        )
        await message.answer(llm_reply.text)
        await react(success=False, message=message)
    else:
        logger.info(
            "DALL-E 3 image generated successfully for chat_id=%s", message.chat.id
        )
        metrics.requests_total.labels(command='pic3', status='success').inc()
        metrics.images_generated.labels(model='dall-e-3').inc()
        await message.chat.do("upload_photo")
        image_from_url = types.URLInputFile(response.b64_or_url)
        caption = f"DALL-E 3 prompt: {prompt}"
        await message.answer_photo(image_from_url, caption=caption)
        await react(success=True, message=message)
    finally:
        metrics.request_duration.labels(command='pic3').observe(time_module.perf_counter() - start_time)


@router.message(
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["pik"]),
)
async def gimme_pikk(message: types.Message, command: types.CommandObject):
    logger.info(
        "Command /pik received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    if command.command in config[message.chat.id].disabled_commands:
        logger.debug("Command /pik is disabled for chat_id=%s", message.chat.id)
        await react(False, message)
        return
    prompt = command.args
    logger.debug("Kandinski image generation requested, prompt=%r", prompt)
    await message.chat.do("upload_photo")
    try:
        response = await ImageResponse.generate(prompt, mode="kandinski")
    except openai.BadRequestError as e:
        logger.warning(
            "Kandinski generation failed for chat_id=%s, prompt=%r, error=%s",
            message.chat.id,
            prompt,
            e,
        )
        messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
        messages_to_send.append(
            (
                "user",
                f'объясни шуткой почему нельзя сгенерировать картинку по запросу "{prompt}"',
            )
        )
        await message.chat.do("typing")
        llm_reply = await TextResponse.generate(
            config=config,
            chat_id=message.chat.id,
            messages=messages_to_send,
        )
        await message.answer(llm_reply.text)
        await react(success=False, message=message)
    else:
        await message.chat.do("upload_photo")
        if response.censored:
            logger.warning(
                "Kandinski response censored for chat_id=%s, prompt=%r",
                message.chat.id,
                prompt,
            )
            messages_to_send = [config.prompt_tuple_for_chat(message.chat.id)]
            messages_to_send.append(
                (
                    "user",
                    f'объясни шуткой почему нельзя сгенерировать картинку по запросу "{prompt}"',  # noqa
                )
            )
            await message.chat.do("typing")
            llm_reply = await TextResponse.generate(
                config=config,
                chat_id=message.chat.id,
                messages=messages_to_send,
            )
            await message.answer(llm_reply.text)
            await react(success=False, message=message)
        else:
            logger.info(
                "Kandinski image generated successfully for chat_id=%s", message.chat.id
            )
            caption = f"Kandinksi-3 prompt: {prompt}"

            im_b64 = response.b64_or_url.encode()
            im_f = base64.decodebytes(im_b64)
            image = types.BufferedInputFile(
                im_f,
                "kandinski.png",
            )

            await message.answer_photo(
                photo=image,
                caption=caption,
            )
            await react(success=True, message=message)


@router.message(
    F.photo,
    config.filter_chat_allowed,
    config.filter_command_not_disabled_for_chat,
    Command(commands=["reimagine"], ignore_mention=True),
)
async def handle_reimagine(
    message: types.Message,
    command: types.CommandObject,
) -> None:
    """Vision + DALL-E 3 reimagine flow."""
    logger.info(
        "Reimagine command: chat_id=%s, user=%s",
        message.chat.id,
        message.from_user.username,
    )

    modification = command.args
    if not modification:
        await message.reply(
            "Please provide a description of how you want to modify the image.\n"
            "Example: <code>/reimagine make it look like a watercolor painting</code>"
        )
        await react(success=False, message=message)
        return

    await message.chat.do("upload_photo")
    progress_msg = await message.answer("Analyzing image with GPT-4 Vision...")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        await progress_msg.edit_text("Reimagining with DALL-E 3...")

        response = await ImageResponse.reimagine(image_bytes, modification)

        await progress_msg.delete()

        if response.success:
            image_from_url = types.URLInputFile(response.b64_or_url)
            await message.answer_photo(
                image_from_url,
                caption=f"Reimagined: {modification}",
            )
            await react(success=True, message=message)
        else:
            await message.answer(response.b64_or_url)
            await react(success=False, message=message)

    except Exception as e:
        logger.error("Reimagine error: %s", e, exc_info=True)
        await progress_msg.edit_text(f"Error: {e}")
        await react(success=False, message=message)
