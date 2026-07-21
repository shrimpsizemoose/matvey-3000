registry := "ghcr.io"
namespace := "shrimpsizemoose"
app := "matvey-3000"
version := `git describe --tags`
bot_service_tag := registry + "/" + namespace + "/" + app + ":" + version
k8s_namespace := "matvey-gang"

# List all available recipes.
_:
  @just --list

# Run the Telegram bot locally.
run:
  uv run python src/bot_handler.py

# Install and synchronize project dependencies.
sync:
  uv sync

# Update the locked dependency versions.
lock:
  uv lock

# Build the bot's Docker image with the current Git version tag.
build-bot:
  docker build -t {{ bot_service_tag }} -f docker/bot.Dockerfile .

# Push the bot's versioned Docker image to the registry.
push-bot:
  docker push {{ bot_service_tag }}

# Run the complete test suite with verbose output.
test:
  uv run pytest -s -vv tests/

# Print the current Git version and full Docker image tag.
echo-version:
  @echo current version tag is {{ version }}
  @echo full tag is {{ bot_service_tag }}

# List pods in the application namespace.
[group('k8s')]
k8s-pods:
  kubectl get pods -n {{ k8s_namespace }}

# List secrets in the application namespace.
[group('k8s')]
k8s-secrets:
  kubectl get secrets -n {{ k8s_namespace }}

# Follow logs from the Matvey bot pods.
[group('k8s')]
k8s-logs-matvey:
  kubectl logs -n {{ k8s_namespace }} -l app=matvey -f

# Follow logs from the Ben bot pods.
[group('k8s')]
k8s-logs-ben:
  kubectl logs -n {{ k8s_namespace }} -l app=ben -f

# Follow logs from the Skrepka bot pods.
[group('k8s')]
k8s-logs-skrepka:
  kubectl logs -n {{ k8s_namespace }} -l app=skrepka -f

# Follow logs from the Redis pods.
[group('k8s')]
k8s-logs-redis:
  kubectl logs -n {{ k8s_namespace }} -l app=redis -f
