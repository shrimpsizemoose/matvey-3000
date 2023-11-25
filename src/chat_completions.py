from dataclasses import dataclass

import openai


@dataclass(frozen=True)
class TextResponse:
    success: bool
    text: str

    @classmethod
    async def generate(cls, client, config, messages):
        if config.provider == config.PROVIDER_OPENAI:
            return await cls._generate_openai(
                client,
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
        try:
            response = await client.chat.completions.create(
                model=config.model,
                messages=messages,
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
