import asyncio
import json
import logging
import os
import textwrap
from dataclasses import dataclass

import anthropic
import httpx
import openai


logger = logging.getLogger(__name__)

openai_client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
anthro_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
yagpt_folder_id = os.getenv('YANDEXGPT_FOLDER_ID', default='NoYaFolder')
yagpt_api_key = os.getenv('YANDEXGPT_API_KEY', default='NoYaKey')
kandinski_api_key = os.getenv('KANDINSKI_API_KEY', default='KandiKeyOopsie')
kandinski_api_secret = os.getenv('KANDINSKI_API_SECRET', default='KandiSecretOopsie')


@dataclass(frozen=True)
class TextResponse:
    success: bool
    text: str

    @classmethod
    async def generate(cls, config, chat_id, messages):
        provider = config.provider_for_chat_id(chat_id)
        model = config.model_for_chat_id(chat_id)
        logger.debug('Generating text response: provider=%s, model=%s, message_count=%d',
                     provider, model, len(messages))
        if provider == config.PROVIDER_OPENAI:
            return await cls._generate_openai(
                openai_client,
                model,
                messages,
            )
        elif provider == config.PROVIDER_ANTHROPIC:
            return await cls._generate_anthropic(
                anthro_client,
                model,
                messages,
            )
        elif provider == config.PROVIDER_YANDEXGPT:
            async with httpx.AsyncClient() as httpx_client:
                return await cls._generate_yandexgpt(
                    httpx_client,
                    model,
                    messages,
                )
        else:
            logger.error('Unsupported provider: %s', provider)
            return cls(success=False, text=f'Unsupported provider: {provider}')

    @classmethod
    async def _generate_openai(cls, client, model, messages):
        logger.debug('OpenAI request: model=%s, message_count=%d', model, len(messages))
        payload = [{'role': role, 'content': text} for role, text in messages]
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=payload,
            )
        except openai.RateLimitError as e:
            logger.warning('OpenAI rate limit error: %s', e)
            return cls(
                success=False,
                text=f'Кажется я подустал и воткнулся в рейт-лимит. Давай сделаем перерыв ненадолго.\n\n{e}',  # noqa
            )
        except openai.BadRequestError as e:
            logger.warning('OpenAI bad request error: %s', e)
            return cls(
                success=False,
                text=f'Beep-bop, кажется я не умею отвечать на такие вопросы:\n\n{e}',  # noqa
            )
        except TimeoutError as e:
            logger.error('OpenAI timeout error: %s', e)
            return cls(
                success=False,
                text=f'Кажется у меня сбоит сеть. Ты попробуй позже, а я пока схожу чаю выпью.\n\n{e}',  # noqa
            )
        else:
            logger.debug('OpenAI response received: model=%s, response_length=%d',
                         model, len(response.choices[0].message.content))
            return cls(
                success=True,
                text=response.choices[0].message.content,
            )

    @classmethod
    async def _generate_anthropic(cls, client, model, messages):
        logger.debug('Anthropic request: model=%s, message_count=%d', model, len(messages))
        user_tag = anthropic.HUMAN_PROMPT
        bot_tag = anthropic.AI_PROMPT
        system = [text for role, text in messages if role == 'system'][0]

        # claude 2.1 might need different format for prompting since it has system prompts
        # full_prompt = f'{system} {user_tag}{human}{bot_tag}'

        # claude instant 1.2 though... Needs a different thing
        prompt = textwrap.dedent(
            """
                Here are a few back and forth messages between user and a bot.
                User messages are in tag <user>, bot messages are in tag <bot>
            """.strip()
        )
        prompt = [f'{user_tag}{prompt}']
        for role, text in messages:
            if role == 'system':
                continue
            prompt.append(f'\n<{role}>{text}</{role}>')
        prompt.append(f'\n{system}')
        prompt.append(
            '\nTake content of last unpaired "user" and use this as completion prompt.'
        )
        prompt.append(f'\nRespond ONLY with text and no tags.{bot_tag}')
        prompt = ''.join(prompt)

        try:
            response = await client.completions.create(
                model=model,
                max_tokens_to_sample=1024,  # no clue about this value
                prompt=prompt,
            )
        except openai.RateLimitError as e:
            logger.warning('Anthropic rate limit error: %s', e)
            return cls(
                success=False,
                text=f'Кажется я подустал и воткнулся в рейт-лимит. Давай сделаем перерыв ненадолго.\n\n{e}',  # noqa
            )
        except openai.BadRequestError as e:
            logger.warning('Anthropic bad request error: %s', e)
            return cls(
                success=False,
                text=f'Beep-bop, кажется я не умею отвечать на такие вопросы:\n\n{e}',  # noqa
            )
        except TimeoutError as e:
            logger.error('Anthropic timeout error: %s', e)
            return cls(
                success=False,
                text=f'Кажется у меня сбоит сеть. Ты попробуй позже, а я пока схожу чаю выпью.\n\n{e}',  # noqa
            )
        else:
            completion = response.completion.replace("<", "[").replace(">", "]")
            logger.debug('Anthropic response received: model=%s, response_length=%d',
                         model, len(completion))
            return cls(
                success=True,
                text=completion,
            )

    @classmethod
    async def _generate_yandexgpt(cls, client, model, messages):
        logger.debug('YandexGPT request: model=%s, message_count=%d', model, len(messages))
        params = {
            'messages': [{'role': role, 'text': text} for role, text in messages],
            'modelUri': f'gpt://{yagpt_folder_id}/{model}',
            'completionOptions': {
                'stream': False,
                'temperature': 0.6,
                'maxTokens': "1000",
            },
        }
        headers = {
            'Authorization': f'Api-Key {yagpt_api_key}',
            'x-folder-id': yagpt_folder_id,
        }
        response = await client.post(
            'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
            json=params,
            headers=headers,
        )
        if response.status_code == 200:
            data = response.json()
            text = data['result']['alternatives'][0]['message']['text']
            logger.debug('YandexGPT response received: model=%s, response_length=%d', model, len(text))
            return cls(
                success=True,
                text=text,
            )
        else:
            logger.error('YandexGPT request failed: status_code=%d, response=%s',
                         response.status_code, response.text[:200])
            return cls(
                success=False,
                text=response.text,
            )


@dataclass(frozen=True)
class ImageResponse:
    success: bool
    b64_or_url: str
    censored: bool = False

    @classmethod
    async def edit(cls, image_bytes: bytes, prompt: str):
        logger.info('Image edit requested: prompt_length=%d, image_size=%d bytes',
                    len(prompt or ''), len(image_bytes))
        client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        try:
            response = await client.images.edit(
                model="dall-e-2",
                image=("image.png", image_bytes, "image/png"),
                prompt=prompt,
                n=1,
                size="512x512",
            )
            logger.info('Image edit successful')
            return cls(success=True, b64_or_url=response.data[0].url)
        except openai.BadRequestError as e:
            logger.warning('Image edit BadRequestError: %s', e)
            return cls(success=False, b64_or_url=f'Не удалось отредактировать картинку: {e}')
        except openai.RateLimitError as e:
            logger.warning('Image edit RateLimitError: %s', e)
            return cls(success=False, b64_or_url=f'Рейт-лимит превышен, попробуй позже: {e}')
        except TimeoutError as e:
            logger.error('Image edit TimeoutError: %s', e)
            return cls(success=False, b64_or_url=f'Таймаут сети, попробуй позже: {e}')

    @classmethod
    async def generate(cls, prompt, mode='dall-e'):
        logger.info('Image generation requested: mode=%s, prompt_length=%d', mode, len(prompt or ''))
        openai_client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        match mode:
            case 'dall-e':
                return await cls._generate_dalle(openai_client, prompt, model='dall-e-2', size='512x512')
            case 'dall-e-3':
                return await cls._generate_dalle(openai_client, prompt, model='dall-e-3', size='1024x1024')
            case 'kandinski':
                async with httpx.AsyncClient() as httpx_client:
                    return await cls._generate_kandinski(httpx_client, prompt)
            case _:
                logger.error('Unsupported image generation mode: %s', mode)
                return cls(success=False, b64_or_url=f'Unsupported provider: {mode}')

    @classmethod
    async def _generate_dalle(cls, client, prompt, model='dall-e-2', size='512x512'):
        logger.debug('DALL-E request: model=%s, size=%s, prompt=%r', model, size, prompt)
        img_gen_reply = await client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=size,
        )
        logger.info('DALL-E image generated successfully: model=%s', model)
        return cls(success=True, b64_or_url=img_gen_reply.data[0].url)

    @classmethod
    async def _generate_kandinski(cls, client, prompt):
        logger.debug('Kandinski request: prompt=%r', prompt)
        BASE_URL = 'https://api-key.fusionbrain.ai/key/api/v1'
        headers = {
            'X-Key': f'Key {kandinski_api_key}',
            'x-Secret': f'Secret {kandinski_api_secret}',
        }
        # pick model
        response = await client.get(
            f'{BASE_URL}/models',
            headers=headers,
        )
        # 2024jan09: only one model supported at the moment anyway
        model_id = response.json()[0]['id']
        logger.debug('Kandinski model selected: model_id=%s', model_id)
        params = {
            'type': 'GENERATE',
            'width': 512,
            'height': 512,
            'num_images': 1,
            'generateParams': {
                'query': prompt,
            },
        }
        data = {
            'model_id': (None, str(model_id)),
            'params': (None, json.dumps(params), 'application/json'),
        }
        response = await client.post(
            f'{BASE_URL}/text2image/run',
            headers=headers,
            files=data,
        )
        run_id = response.json()['uuid']
        logger.debug('Kandinski generation started: run_id=%s', run_id)

        attempts = 10
        delay = 10
        while attempts > 0:
            response = await client.get(
                f'{BASE_URL}/text2image/status/{run_id}', headers=headers
            )
            data = response.json()
            done = data['status'] == 'DONE'
            if done:
                break
            logger.debug('Kandinski generation in progress: run_id=%s, attempts_remaining=%d', run_id, attempts)
            attempts -= 1
            await asyncio.sleep(delay)

        if done:
            logger.info('Kandinski image generated: run_id=%s, censored=%s', run_id, data['censored'])
        else:
            logger.warning('Kandinski generation timed out: run_id=%s', run_id)

        return cls(
            success=done,
            b64_or_url=data['images'][0],
            censored=data['censored'],
        )
