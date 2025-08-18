#!/bin/bash

# Work around for VSCode terminal
unset VIRTUAL_ENV

export QT_API=PySide6
export FORCE_QT_API=PySide6

UV_PROJECT_ENVIRONMENT=.no-pyside-env uv run --no-dev "$@"
