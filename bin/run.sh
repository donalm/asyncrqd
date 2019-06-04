#!/bin/bash

export BASEDIR=$(cd -P -- "$(dirname -- "$(/usr/bin/realpath -- "$(dirname -- "$BASH_SOURCE")")")" && printf '%s\n' "$(pwd -P)")
source "${BASEDIR}/bin/tooling/update_environment.sh"
cd $BASEDIR
echo $SUDO_USER

export LOGDIR=/var/log/asyncrqd
mkdir -p $LOGDIR
chmod 755 $LOGDIR

check_prefix=$(echo "${BASEDIR}" | cut -c1-6)
if [[ "${check_prefix}" == "/home/" ]]; then
    echo "WARNING: This executable will drop privileges and run as the 'daemon' user."
    echo "         If your development environment cannot be accessed by the 'daemon'"
    echo "         user, you may get unexpected ImportErrors"
fi

# Only works with Python3
v=3

# source the virtualenv-created file to get the right python interpreter and modules
activate="${BASEDIR}/venv_py${v}/bin/activate"
source "${activate}"

cd "${BASEDIR}"
tmpdir=$(mktemp -d "${BASEDIR}/_temp_proto_XXX")
if [[ "$?" != "0" ]]; then
    echo "failed to create temp directory"
    exit 1
fi
mkdir -p "${tmpdir}/python/asyncrqd/proto"
mkdir -p "${tmpdir}/asyncrqd/proto"

cp -a "${BASEDIR}/proto"  "${tmpdir}/asyncrqd/."
cd "${tmpdir}/asyncrqd/proto"
sed -i -E 's/^import "/import "asyncrqd\/proto\//' *.proto
cd "${tmpdir}"

python -m grpc_tools.protoc -I./ --python_out=./python --grpc_python_out=./python --python_grpc_out=./python ./asyncrqd/proto/*.proto
touch "${tmpdir}/python/asyncrqd/proto/__init__.py"

if [[ ! -z "${SUDO_USER}" ]]; then
    chown -R $SUDO_USER $tmpdir
fi
cp -a "${tmpdir}/python/asyncrqd/proto" "${BASEDIR}/python/asyncrqd/"
rm -rf "${tmpdir}"

cd "${BASEDIR}/python"
exec "${BASEDIR}/venv_py${v}/bin/python" -m "asyncrqd"
