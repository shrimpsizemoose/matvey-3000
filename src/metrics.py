from prometheus_client import Counter, Histogram, start_http_server

METRICS_PORT = 8000

requests_total = Counter(
    "bot_requests_total",
    "Total bot requests",
    ["command", "status"],
)

request_duration = Histogram(
    "bot_request_duration_seconds",
    "Request duration in seconds",
    ["command"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

tokens_total = Counter(
    "bot_tokens_total",
    "Total tokens used",
    ["provider", "direction"],
)

voice_duration_total = Counter(
    "bot_voice_duration_seconds_total",
    "Total voice audio duration processed",
)

images_generated = Counter(
    "bot_images_generated_total",
    "Total images generated",
    ["model"],
)

errors_total = Counter(
    "bot_errors_total",
    "Total errors",
    ["error_type"],
)


def start_metrics_server() -> None:
    start_http_server(METRICS_PORT)
