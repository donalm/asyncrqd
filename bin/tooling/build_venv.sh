##############################################
#
# This file should not be executed directly.
# It must be called from the rebuild script.
#
##############################################

export BINDIR=$(cd -P -- "$(dirname -- "$(/usr/bin/realpath -- "$(dirname -- "$BASH_SOURCE")")")" && printf '%s\n' "$(pwd -P)")
export BASEDIR="$(dirname $BINDIR)"

majver=$1
executable="python${majver}"
interpreter=$(which $executable 2>/dev/null)
if [[ "$?" != "0" ]]; then
    echo "ERROR: no $executable in \$PATH"
    exit
fi

target="${BASEDIR}/venv_py${majver}"
if [[ ! -e $target ]]; then
    virtualenv -p $interpreter $target
fi

source "${target}/bin/activate"
pip install --upgrade -r "${BASEDIR}/requirements.txt"

outdir="${BASEDIR}/pycue/opencue/compiled_proto"
cd "${BASEDIR}/proto"
python -m grpc_tools.protoc -I=. \
    --python_out="${outdir}" \
    --grpc_python_out="${outdir}" \
    ./*.proto
