#!/usr/bin/env python
"""Basic config data for asyncrqd."""

import os
import traceback

import yaml
from . import log


class ConfigDotNotation(object):
    @classmethod
    def make(cls, data):
        if not isinstance(data, dict):
            return data

        return cls(data)

    def __init__(self, data):
        self._data = data
        cls = self.__class__
        for key, value in data.items():
            self.__setattr__(key, cls.make(value))

    def __getattr__(self, key):
        return None

    def __str__(self):
        return(str(self._data))


class Config(object):
    """Configuration data object."""

    _config_data = None
    _default_filepath = os.path.join(
        os.environ.get("BASEDIR", "."), "config", "asyncrqd.yaml"
    )

    @classmethod
    def init(cls, config_filepath=None):
        cls._config_filepath = config_filepath or cls._default_filepath
        cls.refresh()

    @classmethod
    def dot_notation(cls):
        if cls._config_data is None:
            cls.init()
        return ConfigDotNotation.make(cls._config_data)

    @classmethod
    def refresh(cls):
        with open(cls._config_filepath, "r") as fh:
            try:
                cls._config_data = yaml.safe_load(fh.read())
            except Exception as e:
                log.exception(
                    "failed to refresh config from {}: {}".format(
                        cls._config_filepath, e
                    )
                )

    @classmethod
    def recursive_get(cls, *keys, default=None):
        if cls._config_data is None:
            cls.init()
        return cls._recursive_get(*keys, base=cls._config_data, default=None)

    @classmethod
    def _recursive_get(cls, *keys, base=None, default=None):

        next_key = keys[0]
        keys = keys[1:]

        if not keys:
            # We're at the last value requested
            value = base.get(next_key, default)
            return value

        # The key doesn't exit in the value
        if not next_key in base:
            return default

        base = base[next_key]

        return cls._recursive_get(*keys, base=base, default=default)




get = Config.recursive_get
dot_notation = Config.dot_notation
