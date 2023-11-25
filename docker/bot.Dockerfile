FROM python:3.10-slim-buster

LABEL org.opencontainers.image.source https://github.com/shrimpsizemoose/matvey-3000

WORKDIR /bot

COPY src/bot_handler.py  /bot/
COPY src/config.py /bot/
COPY src/chat_completions.py /bot/

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install the required packages
RUN pip install \
        aiogram==3.2.0 \
        openai==1.3.5 \
        anthropic==0.7.4 \
        pyyaml==6.0

CMD ["python", "/bot/bot_handler.py"]

