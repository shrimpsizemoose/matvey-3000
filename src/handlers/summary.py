import asyncio
import logging

import tiktoken
from aiogram import Router, types
from aiogram.filters import Command, CommandObject

from bot import config, message_store, react
from providers import TextResponse

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    config.filter_summary_enabled,
    Command(commands=["samari", "sammari", "sum", "sosum"]),
)
async def handle_summary_command(message: types.Message, command: CommandObject):
    logger.info(
        "Command /%s (summary) received from chat_id=%s user=%s",
        command.command,
        message.chat.id,
        message.from_user.username,
    )
    tag = f"matvey-3000:history:{config.me_strip_lower}:{message.chat.id}"
    limit = command.args
    limit = -1 if limit is None else int(command.args)
    logger.debug("Fetching messages for summary, tag=%s, limit=%d", tag, limit)
    messages = message_store.fetch_messages(key=tag, limit=limit)
    encoding = tiktoken.encoding_for_model(config.model_for_chat_id(message.chat.id))
    total = len(messages)
    logger.info(
        "Starting summary generation for chat_id=%s, message_count=%d",
        message.chat.id,
        total,
    )
    info_message = await message.answer(f"🤖 Обрабатываю {total} сообщений")

    max_chunk_size = 16385

    def L(x: str) -> int:
        return len(encoding.encode(x))

    def chunk_it(texts: list[str]) -> list[str]:
        chunks = []
        current_chunk = ""

        for tt in texts:
            if L(current_chunk) + L(tt) < max_chunk_size:
                current_chunk += tt + "\n"
            else:
                chunks.append(current_chunk.strip())
                current_chunk = tt + "\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    chunks = chunk_it(texts=map(str, messages))
    logger.debug(
        "Split messages into %d chunks for chat_id=%s", len(chunks), message.chat.id
    )
    progress = await message.answer(f"Обрабатываю 0/{len(chunks)} чанков")

    async def get_summaries(chunks, entity="чанк"):
        prompt = """
You are a helpful assistant who recaps everything that happened in this chat relying on its log.
You use Russian language only, and try to do each recap in no more than 25 sentences, but don't use generalisations too often.
The text is written by other chat members. You retell the most interesting phrases and actions, starting with the name of the actor.
You never lose a chronology of replies and never repeat yourself, while trying to balance out amount of participants' input.
You seldom mention texts produced by chatbots, such as you.
Sometimes you try to be funny by mixing up events and phrases, but never overdo it.
        """
        prompt = prompt.strip()
        total_chunks = len(chunks)
        summaries = []
        for i, chunk in enumerate(chunks, start=1):
            mm = [("system", prompt), ("user", chunk)]
            await progress.edit_text(f"Обрабатываю {entity} {i}/{total_chunks}")
            await message.chat.do("typing")
            llm_reply = await TextResponse.generate(
                config=config,
                chat_id=message.chat.id,
                messages=mm,
            )
            summaries.append(llm_reply.text)
            await asyncio.sleep(0.5)
        return summaries

    summaries = await get_summaries(chunks)
    logger.debug(
        "Generated %d summaries for chat_id=%s", len(summaries), message.chat.id
    )

    final_prompt = """
You are a helpful assistant who recaps everything that happened in this chat relying on its log.
You use Russian language only, and try to do each recap in no more than 25 sentences, but don't use generalisations too often.
The text is written by other chat members. You retell the most interesting phrases and actions, starting with the name of the actor.
You never lose a chronology of replies and never repeat yourself, while trying to balance out amount of participants' input.
You seldom mention texts produced by chatbots, such as you.
Sometimes you try to be funny by mixing up events and phrases, but never overdo it.
After you recap everything, highlight three most outstanding facts or points from the text in a separate paragraph, while not repeating your own words.
"""
    final_prompt = final_prompt.strip()
    L_final_prompt = L(final_prompt)

    final_summary = "\n".join(summaries)
    while L(final_summary) > (max_chunk_size - L_final_prompt):
        final_summary = "\n".join(summaries)
        chunks = chunk_it(texts=summaries)
        summaries = await get_summaries(chunks, entity="предсаммари")
        final_summary = "\n".join(summaries)

    await progress.delete()

    llm_reply = await TextResponse.generate(
        config=config,
        chat_id=message.chat.id,
        messages=[("system", final_prompt), ("user", final_summary)],
    )

    await info_message.delete()

    logger.info(
        "Summary generation completed for chat_id=%s, success=%s",
        message.chat.id,
        llm_reply.success,
    )
    await message.reply(llm_reply.text)
    await react(llm_reply.success, message)
