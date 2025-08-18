#!/bin/bash

set -e

MYPY="uvx mypy"

if [ "$#" -eq 0 ]; then
    # No arguments: check the entire codebase
    targets="plugin.py"
else
    # Arguments given: check only those files
    targets="$@"
fi

$MYPY $targets
