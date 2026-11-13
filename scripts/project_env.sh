#!/usr/bin/env bash
# Source this file from Bash before installing dependencies or running analyses.
export AI_SCI_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
export XDG_CACHE_HOME="$AI_SCI_ROOT/.cache"
export PIP_CACHE_DIR="$AI_SCI_ROOT/.cache/pip"
export TMPDIR="$AI_SCI_ROOT/.tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export PYTHONPYCACHEPREFIX="$AI_SCI_ROOT/.cache/python"
export MPLCONFIGDIR="$AI_SCI_ROOT/.cache/matplotlib"
export JUPYTER_CONFIG_DIR="$AI_SCI_ROOT/.cache/jupyter/config"
export JUPYTER_DATA_DIR="$AI_SCI_ROOT/.cache/jupyter/data"
export JUPYTER_RUNTIME_DIR="$AI_SCI_ROOT/.cache/jupyter/runtime"
mkdir -p "$XDG_CACHE_HOME" "$PIP_CACHE_DIR" "$TMPDIR"     "$PYTHONPYCACHEPREFIX" "$MPLCONFIGDIR"     "$JUPYTER_CONFIG_DIR" "$JUPYTER_DATA_DIR" "$JUPYTER_RUNTIME_DIR"
