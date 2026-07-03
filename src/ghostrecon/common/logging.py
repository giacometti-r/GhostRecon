import logging
import sys

import structlog
from pythonjsonlogger import jsonlogger


def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure structured JSON logs with service context."""

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(request_id)s"
        )
    )
    handler.addFilter(_ServiceContextFilter(service_name))
    root.addHandler(handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(root.level),
        cache_logger_on_first_use=True,
    )


class _ServiceContextFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = self.service_name
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True
