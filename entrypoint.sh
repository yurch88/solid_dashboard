#!/bin/bash
set -e

WG_CONFIG_PATH="${WG_CONFIG_DIR}/${WG_INTERFACE}.conf"
SERVER_PRIVATE_KEY_FILE="${WG_CONFIG_DIR}/server_private.key"
SERVER_PUBLIC_KEY_FILE="${WG_CONFIG_DIR}/server_public.key"

# Установить umask для защиты создаваемых файлов
umask 077

# Генерация ключей, если их нет
if [ ! -f "$SERVER_PRIVATE_KEY_FILE" ]; then
    echo "Generating server private key..."
    wg genkey > "$SERVER_PRIVATE_KEY_FILE"
    chmod 600 "$SERVER_PRIVATE_KEY_FILE"
fi

if [ ! -f "$SERVER_PUBLIC_KEY_FILE" ]; then
    echo "Generating server public key..."
    cat "$SERVER_PRIVATE_KEY_FILE" | wg pubkey > "$SERVER_PUBLIC_KEY_FILE"
fi

SERVER_PRIVATE_KEY=$(cat "$SERVER_PRIVATE_KEY_FILE")
SERVER_PUBLIC_KEY=$(cat "$SERVER_PUBLIC_KEY_FILE")

# Создание конфигурации, если она отсутствует
if [ ! -f "$WG_CONFIG_PATH" ]; then
    echo "Creating WireGuard configuration at $WG_CONFIG_PATH..."
    mkdir -p "$WG_CONFIG_DIR"
    cat <<EOF > "$WG_CONFIG_PATH"
[Interface]
Address = ${WG_DEFAULT_ADDRESS}
PrivateKey = ${SERVER_PRIVATE_KEY}
ListenPort = ${WG_PORT}
DNS = ${WG_DEFAULT_DNS}
SaveConfig = true

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}  # Убедимся, что публичный ключ указан
AllowedIPs = ${WG_ALLOWED_IPS}
EOF
fi

chmod 600 "$WG_CONFIG_PATH"

# Запуск WireGuard интерфейса
if ip link show "$WG_INTERFACE" &>/dev/null; then
    echo "WireGuard interface ${WG_INTERFACE} already exists. Skipping activation."
else
    wg-quick up "$WG_CONFIG_PATH"
fi

exec /app/venv/bin/python3 /app/app.py
