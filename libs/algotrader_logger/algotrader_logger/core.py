from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Generator, Iterable, MutableMapping, Optional, TextIO

_LOG_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar("algotrader_log_context", default={})
_CONFIG_LOCK = threading.Lock()
_CONFIG_SIGNATURE: Optional[str] = None

_DEFAULT_FORMAT = "pretty"
_ALLOWED_FORMATS = {"pretty", "json"}
_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__.keys())
_REDACT_RE = re.compile(r"(token|secret|password|authorization)", re.IGNORECASE)
_COLOR_RESET = "\033[0m"
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
}


class ServiceContextFilter(logging.Filter):
    """Inject service and context fields and suppress noisy logs."""

    def __init__(self, service_name: str, suppress_healthcheck_logs: bool = True) -> None:
        super().__init__()
        self.service_name = service_name
        self.suppress_healthcheck_logs = suppress_healthcheck_logs

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service_name

        context_data = _LOG_CONTEXT.get()
        if context_data:
            for key, value in context_data.items():
                if not hasattr(record, key):
                    setattr(record, key, value)

        if self.suppress_healthcheck_logs and _is_healthcheck_access_log(record):
            return False

        return True


class PrettyFormatter(logging.Formatter):
    def __init__(self, colorize: bool = False) -> None:
        super().__init__()
        self.colorize = colorize

    def format(self, record: logging.LogRecord) -> str:
        timestamp = _format_timestamp(record.created)
        message = record.getMessage()
        level = record.levelname
        if self.colorize:
            color = _LEVEL_COLORS.get(level)
            if color:
                level = "{}{}{}".format(color, level, _COLOR_RESET)

        line = "{} | {:<8} | {} | {}".format(
            timestamp,
            level,
            record.name,
            message,
        )

        extras = _extract_extra_fields(record)
        if extras:
            line = "{} | {}".format(line, _format_key_values(extras))

        if record.exc_info:
            line = "{}\n{}".format(line, self.formatException(record.exc_info))

        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": _format_timestamp(record.created),
            "level": record.levelname,
            "service": getattr(record, "service", "unknown-service"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = _extract_extra_fields(record)
        if extras:
            payload.update(extras)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), default=str)


class RequestLoggingMiddleware:
    """Low-overhead ASGI middleware for request summary logging."""

    def __init__(self, app: Any, logger_name: str = "http.request", include_healthcheck: bool = False) -> None:
        self.app = app
        self.logger = get_logger(logger_name)
        self.include_healthcheck = include_healthcheck

    async def __call__(self, scope: MutableMapping[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        request_id = _extract_request_id(scope.get("headers", []))
        should_log = self.include_healthcheck or path != "/health"

        start = perf_counter()
        status_code_holder: Dict[str, int] = {}

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                status_code_holder["value"] = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("utf-8")))
                message["headers"] = headers
            await send(message)

        failed = False
        with bind_context(request_id=request_id):
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                failed = True
                duration_ms = int((perf_counter() - start) * 1000)
                self.logger.exception(
                    "request_failed",
                    extra={
                        "event": "request_failed",
                        "method": method,
                        "path": path,
                        "status_code": 500,
                        "duration_ms": duration_ms,
                    },
                )
                raise
            finally:
                if should_log and not failed:
                    duration_ms = int((perf_counter() - start) * 1000)
                    status_code = status_code_holder.get("value", 500)
                    self.logger.info(
                        "request_complete",
                        extra={
                            "event": "request_complete",
                            "method": method,
                            "path": path,
                            "status_code": status_code,
                            "duration_ms": duration_ms,
                        },
                    )


def configure_logging(
    service_name: str,
    level: str = "INFO",
    format: str = _DEFAULT_FORMAT,
    capture_warnings: bool = True,
    suppress_healthcheck_logs: bool = True,
    colorize: Optional[bool] = None,
    stream: Optional[TextIO] = None,
) -> None:
    """Configure process-wide logging for a service."""

    normalized_level = _normalize_level(level)
    normalized_format = _normalize_format(format)
    stream = stream or sys.stdout
    if colorize is None:
        default_colorize = bool(getattr(stream, "isatty", lambda: False)())
        if not default_colorize and os.getenv("MODE", "").lower() == "development":
            default_colorize = True
        colorize = _normalize_bool(
            os.getenv("{}_LOG_COLOR".format(service_name.upper().replace("-", "_"))),
            default=_normalize_bool(os.getenv("LOG_COLOR"), default=default_colorize),
        )

    signature = "{}:{}:{}:{}:{}:{}".format(
        service_name,
        normalized_level,
        normalized_format,
        suppress_healthcheck_logs,
        colorize,
        id(stream),
    )

    global _CONFIG_SIGNATURE
    with _CONFIG_LOCK:
        if _CONFIG_SIGNATURE == signature:
            return

        handler = logging.StreamHandler(stream)
        handler.setLevel(normalized_level)
        if normalized_format == "json":
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(PrettyFormatter(colorize=colorize))
        handler.addFilter(
            ServiceContextFilter(
                service_name=service_name,
                suppress_healthcheck_logs=suppress_healthcheck_logs,
            )
        )

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(normalized_level)
        root_logger.addHandler(handler)

        # Force uvicorn loggers to flow through root so formatting is consistent.
        for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            uvicorn_logger = logging.getLogger(logger_name)
            uvicorn_logger.handlers.clear()
            uvicorn_logger.propagate = True
            uvicorn_logger.setLevel(normalized_level)

        if capture_warnings:
            logging.captureWarnings(True)

        _CONFIG_SIGNATURE = signature


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a module logger."""

    return logging.getLogger(name)


@contextmanager
def bind_context(**fields: Any) -> Generator[None, None, None]:
    """Bind contextual fields to all logs in the current context."""

    current = dict(_LOG_CONTEXT.get())
    current.update(fields)
    token = _LOG_CONTEXT.set(current)
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


def _normalize_level(value: str) -> int:
    if not value:
        return logging.INFO
    level = logging.getLevelName(value.upper())
    if isinstance(level, int):
        return level
    return logging.INFO


def _normalize_format(value: str) -> str:
    normalized = (value or _DEFAULT_FORMAT).lower().strip()
    if normalized not in _ALLOWED_FORMATS:
        return _DEFAULT_FORMAT
    return normalized


def _normalize_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _format_timestamp(created: float) -> str:
    dt = datetime.fromtimestamp(created, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _extract_request_id(headers: Iterable[Any]) -> str:
    for key, value in headers:
        if key == b"x-request-id":
            try:
                return value.decode("utf-8")
            except Exception:
                break
    return uuid.uuid4().hex[:12]


def _is_healthcheck_access_log(record: logging.LogRecord) -> bool:
    if record.name != "uvicorn.access":
        return False

    args = record.args
    if isinstance(args, tuple) and len(args) >= 3:
        try:
            path = str(args[2])
            return path == "/health"
        except Exception:
            return False

    message = record.getMessage()
    return " /health " in message or " /health\"" in message


def _extract_extra_fields(record: logging.LogRecord) -> Dict[str, Any]:
    extras: Dict[str, Any] = {}

    for key, value in record.__dict__.items():
        if key in _STANDARD_RECORD_FIELDS:
            continue
        if key in {"service"}:
            continue
        if key in {"message", "asctime"}:
            continue
        if value is None:
            continue
        extras[key] = _sanitize_field(key, value)

    return extras


def _sanitize_field(key: str, value: Any) -> Any:
    if _REDACT_RE.search(key):
        return "***"

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for nested_key, nested_value in value.items():
            nested_name = str(nested_key)
            sanitized[nested_name] = _sanitize_field(nested_name, nested_value)
        return sanitized

    if isinstance(value, (list, tuple)):
        return [_sanitize_field(key, item) for item in value]

    return str(value)


def _format_key_values(values: Dict[str, Any]) -> str:
    parts = []
    for key in sorted(values.keys()):
        parts.append("{}={}".format(key, json.dumps(values[key], separators=(",", ":"), default=str)))
    return " ".join(parts)
