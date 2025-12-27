#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$DIR/venv/bin/activate"
export PYTHONUNBUFFERED=1

# $1 is URL, $2 is DataPath
if [ -n "$2" ]; then
    cd "$2"
fi

syrics "$1"
