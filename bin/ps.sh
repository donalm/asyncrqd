#!/bin/bash

export BASEDIR=$(cd -P -- "$(dirname -- "$(/usr/bin/realpath -- "$(dirname -- "$BASH_SOURCE")")")" && printf '%s\n' "$(pwd -P)")
source "${BASEDIR}/bin/tooling/update_environment.sh"
cd $BASEDIR

# Only works with Python3
v=3

# source the virtualenv-created file to get the right python interpreter and modules
activate="${BASEDIR}/venv_pypy${v}/bin/activate"
source "${activate}"

cd "${BASEDIR}"

export PYTHONIOENCODING="UTF-8"
export PYTHONPATH="${BASEDIR}/python"
exec "${BASEDIR}/venv_pypy${v}/bin/python" -u "${BASEDIR}/bin/py/process_test.py"
