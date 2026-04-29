import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            payload.update(record.extra_data)
        return json.dumps(payload, ensure_ascii=False)


class TokenOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == "app.token"


class ExcludeTokenFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name != "app.token"


def configure_logging(level: str = "INFO", reduce_noise: bool = True) -> None:
    formatter = JsonFormatter()
    logs_dir = Path("./logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ExcludeTokenFilter())

    ops_file_handler = logging.FileHandler(logs_dir / "ops.log", encoding="utf-8")
    ops_file_handler.setFormatter(formatter)
    ops_file_handler.addFilter(ExcludeTokenFilter())

    token_file_handler = logging.FileHandler(logs_dir / "token.log", encoding="utf-8")
    token_file_handler.setFormatter(formatter)
    token_file_handler.addFilter(TokenOnlyFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [console_handler, ops_file_handler, token_file_handler]

    if reduce_noise:
        # Keep only key application logs by default.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("chromadb").setLevel(logging.WARNING)
        logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
