#!/bin/bash

export PYTHONPATH="${BASEDIR}/bin/tooling/pythonpath:${PYTHONPATH}"
export PATH="${BASEDIR}/bin/tooling/pythonpath/bin:${PATH}"
export CUEBOT_HOSTNAME="localhost"
export CUE_FS_ROOT=/var/opencue
export PYTHONDONTWRITEBYTECODE=1
export OPENCUE_CONF="${BASEDIR}/bin/tooling/opencue_conf.yaml"
