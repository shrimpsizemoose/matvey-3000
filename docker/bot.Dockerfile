FROM python:3.10-slim-buster

LABEL org.opencontainers.image.source https://github.com/shrimpsizemoose/matvey-3000

WORKDIR /bot

COPY src/bot_handler.py  /bot/
COPY src/config.py /bot/

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install the required packages
RUN pip install -U --pre aiogram && \
    pip install openai pyyaml 

CMD ["python", "/bot/bot_handler.py"]

