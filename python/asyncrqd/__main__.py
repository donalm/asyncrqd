#!/usr/bin/env python
"""Main entry point for the Async RQD Daemon."""

from . import log
from . import grpc_server

logger = log.get_logger()
logger.error("starting asyncrqd")

grpc_server.run()
