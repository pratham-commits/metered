import os
import time

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, make_asgi_app

from rideshare.logging_setup import configure

REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests",
    ["service", "method", "path", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP latency",
    ["service", "method", "path", "status"],
)


def install(app: FastAPI, service_name: str, ready_check=None) -> None:
    os.environ["SERVICE_NAME"] = service_name
    log = configure()

    @app.middleware("http")
    async def metrics(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        labels = (service_name, request.method, path, str(response.status_code))
        REQUESTS.labels(*labels).inc()
        LATENCY.labels(*labels).observe(time.perf_counter() - started)
        return response

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": service_name}

    @app.get("/readyz")
    def readyz():
        if ready_check is not None:
            ready_check()
        return {"ok": True}

    app.mount("/metrics", make_asgi_app())
    log.info("service started", extra={"event": "startup"})
