"""
app/core/logging.py
-------------------
Centralised structlog configuration.

Usage
-----
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("receipt_saved", receipt_id=42, merchant="REWE")

In development/testing you get a pretty, colourised console output.
In production (ENVIRONMENT=production) you get newline-delimited JSON,
which is compatible with Datadog, Loki, CloudWatch, etc.
"""

import logging
import sys
import structlog
from app.core.config import settings


def configure_logging() -> None:
    """
    Call once at application startup (in the FastAPI lifespan handler and
    at the top of the Celery worker module).
    """
    is_production = settings.ENVIRONMENT == "production"

    shared_processors = [
        # Add log level as a string field
        structlog.stdlib.add_log_level,
        # Add the logger name (module path)
        structlog.stdlib.add_logger_name,
        # ISO-8601 timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Render exception tracebacks as strings
        structlog.processors.format_exc_info,
        # Merge extra context added via structlog.contextvars.bind_contextvars()
        structlog.contextvars.merge_contextvars,
    ]

    if is_production:
        # JSON renderer for log aggregation platforms
        renderer = structlog.processors.JSONRenderer()
    else:
        # Pretty colourised output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            # Prepare for stdlib logging bridge
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # These run on every record, including those from third-party libs
        foreign_pre_chain=shared_processors,
        processors=[
            # Remove the _record key added by the bridge
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Clear any handlers installed by uvicorn / celery before we attach ours
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Suppress noisy third-party loggers that flood the output
    for noisy in ("httpx", "httpcore", "aiogram", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
