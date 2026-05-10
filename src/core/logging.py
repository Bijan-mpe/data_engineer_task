"""
Structured logging setup using structlog.
Call setup_logging() once at app startup.
Then use get_logger() in every module.
"""

import logging

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structlog for the whole application.
    Call this once at startup in main.py.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR.
    """

    # force=True reconfigures the root logger even if handlers already exist,
    # which is necessary when setup_logging() is called more than once (e.g. tests).
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
        force=True,
    )

    # Configure structlog processors
    # Processors run in order, each one transforms the log entry
    structlog.configure(
        processors=[
            # Add logger name to every entry
            structlog.stdlib.add_logger_name,
            # Add log level to every entry
            structlog.stdlib.add_log_level,
            # Add timestamp to every entry
            structlog.processors.TimeStamper(fmt="iso"),
            # If there is an exception, format it nicely
            structlog.processors.format_exc_info,
            # Final step: render as JSON
            structlog.processors.JSONRenderer(),
        ],
        # Use Python's standard logging under the hood
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger bound to a specific module name.
    The name appears in every log line so you know where it came from.

    Args:
        name: Module name. Use __name__ for automatic naming.

    Returns:
        Bound structlog logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("pipeline.started", filename="corporates_A_1.xlsm")
        logger.error("pipeline.failed", error="missing field")
    """
    return structlog.get_logger(name)
