#!/usr/bin/env python
"""Basic config data for asyncrqd."""

import traceback

import yaml
from . import log


class Config(object):
    def __init__(self, config_file):
        self._config_file = config_file
        self.refresh()

    def refresh(self):
        with open(self._config_file) as fh:
            try:
                self._config_data = yaml.load(fh.read())
            except Exception as e:
                log.exception(
                    "failed to refresh config from {}: {}".format(self._config_file, e)
                )

    def get(self, key, value=None):
        return self._config_data.get(key, value)

    def set(self, key, value):
        raise NotImplementedError("config object is immutable")
