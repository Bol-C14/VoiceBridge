from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Iterator


DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
    enable_file: bool = False,
) -> None:
    """
    Configure root logging for console and optional file output.
    Safe to call multiple times; existing handlers will be replaced.
    """
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if enable_file:
        target = log_file or Path("logs/voicebridge.log")
        target.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(target))

    logging.basicConfig(level=level, format=DEFAULT_LOG_FORMAT, handlers=handlers)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def log_timing(logger: logging.Logger, operation: str, **fields: object) -> Iterator[None]:
    """
    Log duration for an operation; emits both success and exception paths.
    """
    start = perf_counter()
    try:
        yield
    except Exception:
        duration_ms = int((perf_counter() - start) * 1000)
        logger.exception("Failed %s (%d ms)", operation, duration_ms, extra=fields)
        raise
    else:
        duration_ms = int((perf_counter() - start) * 1000)
        logger.info("Completed %s (%d ms)", operation, duration_ms, extra=fields)
