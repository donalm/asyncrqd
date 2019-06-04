#!/usr/bin/env python
"""Basic config data for asyncrqd."""

import os
import traceback

import yaml
from . import log


class Config(object):
    """Configuration data object."""

    _config = None
    _default_filepath = os.path.join(
        os.environ.get("BASEDIR", "."), "config", "asyncrqd.yaml"
    )

    @classmethod
    def init(cls, config_filepath=None):
        cls._config_filepath = config_filepath or cls._default_filepath
        cls.refresh()

    @classmethod
    def refresh(cls):
        with open(cls._config_filepath, "r") as fh:
            try:
                cls._config_data = yaml.load(fh.read())
            except Exception as e:
                log.exception(
                    "failed to refresh config from {}: {}".format(
                        cls._config_filepath, e
                    )
                )

    @classmethod
    def get(cls, key, default_value=None):
        if cls._config is None:
            cls.init()
        return cls._config_data.get(key, default_value)

get = Config.get
