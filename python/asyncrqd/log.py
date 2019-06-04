#!/usr/bin/env python

import logging
import logging.handlers

import structlog
from structlog import configure as structlog_configure
from structlog.stdlib import LoggerFactory as StdLibLoggerFactory

from . import config


class AsyncRQDLogger(object):
    """Configure logging."""

    _logger = None
    _log_filepath = None

    @classmethod
    def get_logger(cls, *args, **kwargs):
        """Return a configured logger object."""
        if cls._logger is not None:
            return cls._logger

        structlog_configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.render_to_log_kwargs,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        cls.log_filepath = cls._log_filepath or config.get("daemon", {}).get(
            "log", {}
        ).get("path", "/var/log/asyncrqd/asyncrqd.log")
        handler = logging.handlers.TimedRotatingFileHandler(
            cls.log_filepath, "midnight", 1
        )
        handler.setLevel(logging.DEBUG)

        cls._logger = structlog.get_logger(*args, **kwargs)
        cls._logger.addHandler(handler)
        return cls._logger


get_logger = AsyncRQDLogger.get_logger
