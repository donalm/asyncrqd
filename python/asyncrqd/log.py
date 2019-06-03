#!/usr/bin/env python

import logging
import logging.handlers
logging.handlers.TimedRotatingFileHandler("/tmp/donal.log", "midnight",1)

from . import config

logging.handlers.TimedRotatingFileHandler(filename,

def exception(*args, **kwargs):
    Logger.exception(*args, **kwargs):
