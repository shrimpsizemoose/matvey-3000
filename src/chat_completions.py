import os
from dataclasses import dataclass

import openai


@dataclass(frozen=True)
class TextResponse:
    success: bool
    text: str

    @classmethod
    async def generate(cls, config, messages):
        if config.provider == config.PROVIDER_OPENAI:
            openai_client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            return await cls._generate_openai(
                openai_client,
                config,
                messages,
            )
        else:
            return cls(
                success=False,
                text=f'Unsupported provider: {config.provider}'
            )

    @classmethod
    async def _generate_openai(cls, client, config, messages):
        payload = [
            {'role': role, 'content': text}
            for role, text in messages
        ]
        try:
            response = await client.chat.completions.create(
                model=config.model,
                messages=payload,
            )
        except openai.RateLimitError as e:
            return cls(
                success=False,
                text=f'Кажется я подустал и воткнулся в рейт-лимит. Давай сделаем перерыв ненадолго.\n\n{e}',  # noqa
            )
        except openai.BadRequestError as e:
            return cls(
                success=False,
                text=f'Beep-bop, кажется я не умею отвечать на такие вопросы:\n\n{e}',  # noqa
             )
        except TimeoutError as e:
            return cls(
                success=False,
                text=f'Кажется у меня сбоит сеть. Ты попробуй позже, а я пока схожу чаю выпью.\n\n{e}',  # noqa
            )
        else:
            return cls(
                success=True,
                text=response.choices[0].message.content,
            )


@dataclass(frozen=True)
class ImageResponse:
    success: bool
    image_url: str

    @classmethod
    async def generate(cls, prompt):
        # no other providers yet so meh
        openai_client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        return await cls._generate_openai(openai_client, prompt)

    @classmethod
    async def _generate_openai(cls, client, prompt):
        img_gen_reply = await client.images.generate(
            prompt=prompt,
            n=1,
            size='512x512',
        )
        return cls(success=True, image_url=img_gen_reply.data[0].url)

