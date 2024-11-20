#!/bin/bash
set -e

WG_CONFIG_PATH="${WG_CONFIG_DIR}/${WG_INTERFACE}.conf"

if [ ! -f "${WG_CONFIG_DIR}/privatekey" ]; then
    echo "Generating WireGuard private and public keys..."
    wg genkey > "${WG_CONFIG_DIR}/privatekey"
    cat "${WG_CONFIG_DIR}/privatekey" | wg pubkey > "${WG_CONFIG_DIR}/publickey"
fi

WG_PRIVATE_KEY=$(cat "${WG_CONFIG_DIR}/privatekey")
WG_PUBLIC_KEY=$(cat "${WG_CONFIG_DIR}/publickey")

if [ ! -f "$WG_CONFIG_PATH" ]; then
    echo "Creating WireGuard configuration at $WG_CONFIG_PATH..."
    mkdir -p "${WG_CONFIG_DIR}"
    cat <<EOF > "$WG_CONFIG_PATH"
[Interface]
Address = ${WG_DEFAULT_ADDRESS}
PrivateKey = ${WG_PRIVATE_KEY}
ListenPort = ${WG_PORT}
SaveConfig = true
EOF
fi

chmod 600 "$WG_CONFIG_PATH"

if ip link show "${WG_INTERFACE}" &>/dev/null; then
    echo "WireGuard interface ${WG_INTERFACE} already exists. Skipping activation."
else
    wg-quick up "$WG_CONFIG_PATH"
fi

exec /app/venv/bin/python3 /app/app.py
