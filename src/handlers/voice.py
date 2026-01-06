import logging
import time as time_module

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot, config, message_store, react
import metrics
from providers import AudioResponse

logger = logging.getLogger(__name__)
router = Router()

MAX_VOICE_DURATION_SECONDS = 300


@router.message(
    F.voice,
    config.filter_voice_enabled,
)
async def handle_voice_message(message: types.Message) -> None:
    logger.info(
        "Voice message received: chat_id=%s, user=%s, duration=%s",
        message.chat.id,
        message.from_user.username,
        message.voice.duration,
    )
    start_time = time_module.perf_counter()

    if message.voice.duration > MAX_VOICE_DURATION_SECONDS:
        await message.reply(
            f"Voice message too long ({message.voice.duration}s). "
            f"Max duration: {MAX_VOICE_DURATION_SECONDS // 60} minutes."
        )
        metrics.requests_total.labels(command='voice', status='rejected').inc()
        await react(success=False, message=message)
        return

    await message.chat.do("typing")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_bytes = await bot.download_file(file.file_path)
        audio_data = file_bytes.read()

        response = await AudioResponse.transcribe(audio_data, filename="voice.ogg")

        if response.success:
            transcription = response.data
            logger.info(
                "Voice transcribed for chat_id=%s, length=%d",
                message.chat.id,
                len(transcription),
            )
            metrics.requests_total.labels(command='voice', status='success').inc()
            metrics.voice_duration_total.inc(message.voice.duration)
            await message.reply(f"<b>Transcription:</b>\n{transcription}")
            await react(success=True, message=message)
        else:
            logger.warning(
                "Voice transcription failed for chat_id=%s: %s",
                message.chat.id,
                response.data,
            )
            metrics.requests_total.labels(command='voice', status='error').inc()
            await message.reply(f"Transcription failed: {response.data}")
            await react(success=False, message=message)

    except Exception as e:
        logger.error("Voice transcription error: %s", e, exc_info=True)
        metrics.requests_total.labels(command='voice', status='error').inc()
        metrics.errors_total.labels(error_type='exception').inc()
        await message.reply(f"Error: {e}")
        await react(success=False, message=message)
    finally:
        metrics.request_duration.labels(command='voice').observe(time_module.perf_counter() - start_time)


@router.message(
    F.video_note,
    config.filter_voice_enabled,
)
async def handle_video_note_message(message: types.Message) -> None:
    logger.info(
        "Video note received: chat_id=%s, user=%s, duration=%s",
        message.chat.id,
        message.from_user.username,
        message.video_note.duration,
    )
    start_time = time_module.perf_counter()

    if message.video_note.duration > MAX_VOICE_DURATION_SECONDS:
        await message.reply(
            f"Video note too long ({message.video_note.duration}s). "
            f"Max duration: {MAX_VOICE_DURATION_SECONDS // 60} minutes."
        )
        metrics.requests_total.labels(command='video_note', status='rejected').inc()
        await react(success=False, message=message)
        return

    await message.chat.do("typing")

    try:
        file = await bot.get_file(message.video_note.file_id)
        file_bytes = await bot.download_file(file.file_path)
        video_data = file_bytes.read()

        response = await AudioResponse.transcribe(video_data, filename="video_note.mp4")

        if response.success:
            transcription = response.data
            logger.info(
                "Video note transcribed for chat_id=%s, length=%d",
                message.chat.id,
                len(transcription),
            )
            metrics.requests_total.labels(command='video_note', status='success').inc()
            metrics.voice_duration_total.inc(message.video_note.duration)
            await message.reply(f"<b>Transcription:</b>\n{transcription}")
            await react(success=True, message=message)
        else:
            logger.warning(
                "Video note transcription failed for chat_id=%s: %s",
                message.chat.id,
                response.data,
            )
            metrics.requests_total.labels(command='video_note', status='error').inc()
            await message.reply(f"Transcription failed: {response.data}")
            await react(success=False, message=message)

    except Exception as e:
        logger.error("Video note transcription error: %s", e, exc_info=True)
        metrics.requests_total.labels(command='video_note', status='error').inc()
        metrics.errors_total.labels(error_type='exception').inc()
        await message.reply(f"Error: {e}")
        await react(success=False, message=message)
    finally:
        metrics.request_duration.labels(command='video_note').observe(time_module.perf_counter() - start_time)


def get_tts_voice_keyboard(current_voice: str, original_message_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for voice in config.TTS_VOICES:
        if voice == current_voice:
            builder.button(text=f"✓ {voice}", callback_data="noop")
        else:
            builder.button(text=voice, callback_data=f"tts:{voice}:{original_message_id}")
    builder.adjust(3)
    return builder.as_markup()


def parse_tts_voice_and_text(args: str, default_voice: str) -> tuple[str, str]:
    if not args:
        return default_voice, ""

    parts = args.split(None, 1)
    if not parts:
        return default_voice, args

    first_word = parts[0].rstrip(':').lower()
    if first_word in config.TTS_VOICES:
        text = parts[1] if len(parts) > 1 else ""
        return first_word, text

    return default_voice, args


@router.message(
    config.filter_voice_enabled,
    Command(commands=["tts"]),
)
async def handle_tts_command(message: types.Message, command: types.CommandObject) -> None:
    logger.info(
        "Command /tts received from chat_id=%s user=%s",
        message.chat.id,
        message.from_user.username,
    )
    start_time = time_module.perf_counter()

    chat_config = config[message.chat.id]
    voice, text = parse_tts_voice_and_text(command.args, chat_config.tts_voice)

    if not text:
        voices_list = ", ".join(config.TTS_VOICES)
        await message.reply(
            "Please provide text to convert to speech.\n"
            f"Example: <code>/tts Hello, how are you?</code>\n"
            f"Or with voice: <code>/tts nova: Hello!</code>\n"
            f"Available voices: {voices_list}"
        )
        metrics.requests_total.labels(command='tts', status='rejected').inc()
        await react(success=False, message=message)
        return

    await message.chat.do("record_voice")

    try:
        response = await AudioResponse.text_to_speech(text, voice=voice)

        if response.success:
            audio_data = response.data
            logger.info(
                "TTS generated for chat_id=%s, voice=%s, audio_size=%d",
                message.chat.id,
                voice,
                len(audio_data),
            )
            metrics.requests_total.labels(command='tts', status='success').inc()

            message_store.store_tts_text(
                bot_username=config.me_strip_lower,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                message_id=message.message_id,
                text=text,
            )

            voice_file = types.BufferedInputFile(audio_data, filename="speech.ogg")
            keyboard = get_tts_voice_keyboard(voice, message.message_id)
            await message.reply_voice(voice_file, reply_markup=keyboard)
            await react(success=True, message=message)
        else:
            logger.warning(
                "TTS failed for chat_id=%s: %s",
                message.chat.id,
                response.data,
            )
            metrics.requests_total.labels(command='tts', status='error').inc()
            await message.reply(f"TTS failed: {response.data}")
            await react(success=False, message=message)

    except Exception as e:
        logger.error("TTS error: %s", e, exc_info=True)
        metrics.requests_total.labels(command='tts', status='error').inc()
        metrics.errors_total.labels(error_type='exception').inc()
        await message.reply(f"Error: {e}")
        await react(success=False, message=message)
    finally:
        metrics.request_duration.labels(command='tts').observe(time_module.perf_counter() - start_time)


@router.callback_query(F.data.startswith("tts:"))
async def handle_tts_voice_callback(callback: types.CallbackQuery) -> None:
    _, voice, original_msg_id = callback.data.split(":")
    original_msg_id = int(original_msg_id)

    text = message_store.get_tts_text(
        bot_username=config.me_strip_lower,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        message_id=original_msg_id,
    )

    if not text:
        await callback.answer("Text expired, please send /tts again", show_alert=True)
        return

    await callback.answer(f"Generating with {voice}...")
    await callback.message.chat.do("record_voice")

    try:
        response = await AudioResponse.text_to_speech(text, voice=voice)

        if response.success:
            voice_file = types.BufferedInputFile(response.data, filename="speech.ogg")
            keyboard = get_tts_voice_keyboard(voice, original_msg_id)
            await callback.message.answer_voice(voice_file, reply_markup=keyboard)
        else:
            await callback.message.answer(f"TTS failed: {response.data}")

    except Exception as e:
        logger.error("TTS callback error: %s", e, exc_info=True)
        await callback.message.answer(f"Error: {e}")
