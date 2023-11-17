REGISTRY=ghcr.io
NAMESPACE=shrimpsizemoose
APP=matvey-3000
VERSION=0.1.0

BOT_SERVICE_TAG=${REGISTRY}/${NAMESPACE}/matvey:${VERSION}

@build-bot:
	docker build -t ${BOT_SERVICE_TAG} -f docker/bot.Dockerfile .

@push-bot:
	docker push ${BOT_SERVICE_TAG}
@test:
	PYTHONPATH=src pytest -s -vv tests/
