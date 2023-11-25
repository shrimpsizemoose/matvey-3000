REGISTRY=ghcr.io
NAMESPACE=shrimpsizemoose
APP=matvey-3000
VERSION=$(shell git describe --tags)

BOT_SERVICE_TAG=${REGISTRY}/${NAMESPACE}/${APP}:${VERSION}

run:
	PYTHONPATH=src python -B src/bot_handler.py

@build-bot:
	docker build -t ${BOT_SERVICE_TAG} -f docker/bot.Dockerfile .

@push-bot:
	docker push ${BOT_SERVICE_TAG}
@test:
	PYTHONPATH=src pytest -s -vv tests/

echo-version:
	@echo current version tag is ${VERSION}
	@echo full tag is ${BOT_SERVICE_TAG}
