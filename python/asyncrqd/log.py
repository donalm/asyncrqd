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
        print(config.get("daemon"))
        cls.log_filepath = cls._log_filepath or config.get("daemon", {}).get("log", {}).get(
            "path", "/var/log/asyncrqd/asyncrqd.log"
        )
        handler = logging.handlers.TimedRotatingFileHandler(
            cls.log_filepath, "midnight", 1
        )
        handler.setLevel(logging.DEBUG)

        structlog_configure(logger_factory=StdLibLoggerFactory())
        cls._logger = structlog.get_logger(*args, **kwargs)
        cls._logger.addHandler(handler)
        return cls._logger

get_logger = AsyncRQDLogger.get_logger
