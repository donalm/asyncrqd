#!/bin/bash

export BASEDIR=$(cd -P -- "$(dirname -- "$(/usr/bin/realpath -- "$(dirname -- "$BASH_SOURCE")")")" && printf '%s\n' "$(pwd -P)")
source "${BASEDIR}/bin/tooling/update_environment.sh"

if [[ ! -e "${CUE_FS_ROOT}" ]]; then
    sudo mkdir -p "${CUE_FS_ROOT}"
fi

"${BASEDIR}/bin/tooling/build_venv.sh" "3"
