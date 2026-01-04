FROM python:3.11-slim-buster

LABEL org.opencontainers.image.source https://github.com/shrimpsizemoose/matvey-3000

WORKDIR /bot

COPY src/bot_handler.py  /bot/
COPY src/config.py /bot/
COPY src/chat_completions.py /bot/
COPY src/message_store.py /bot/
COPY scripts/dump_data_from_storage.py /bot/

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ARG GIT_SHA
ENV GIT_SHA_ENV=$GIT_SHA

# Install the required packages
RUN pip install \
        aiogram==3.6.0 \
        anthropic==0.16.0 \
        hiredis==2.3.2 \
        httpx==0.27.0 \
        openai==1.30.0 \
        Pillow==10.3.0 \
        redis==5.0.4 \
        tiktoken==0.7.0

CMD ["python", "/bot/bot_handler.py"]

