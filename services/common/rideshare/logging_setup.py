import json
import logging
import os


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "service": os.environ.get("SERVICE_NAME", "unknown"),
            "message": record.getMessage(),
            "ride_id": getattr(record, "ride_id", ""),
            "event": getattr(record, "event", ""),
        }
        return json.dumps(payload)


def configure() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return logging.getLogger(os.environ.get("SERVICE_NAME", "rideshare"))
