REGISTRY=ghcr.io
NAMESPACE=shrimpsizemoose
APP=matvey-3000
VERSION=$(shell git describe --tags)

BOT_SERVICE_TAG=${REGISTRY}/${NAMESPACE}/${APP}:${VERSION}

run:
	uv run python src/bot_handler.py

sync:
	uv sync

lock:
	uv lock

@build-bot:
	docker build -t ${BOT_SERVICE_TAG} -f docker/bot.Dockerfile .

@push-bot:
	docker push ${BOT_SERVICE_TAG}
@test:
	uv run pytest -s -vv tests/

echo-version:
	@echo current version tag is ${VERSION}
	@echo full tag is ${BOT_SERVICE_TAG}
