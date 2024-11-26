#!/bin/bash
set -e

if [ ! -d "$WG_CONFIG_DIR" ]; then
    echo "Error: WireGuard configuration directory $WG_CONFIG_DIR does not exist."
    exit 1
fi

source /app/venv/bin/activate

exec python3 app.py
