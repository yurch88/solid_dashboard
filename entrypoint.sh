#!/bin/bash
set -e

WG_CONFIG_PATH="${WG_CONFIG_DIR}/${WG_INTERFACE}.conf"
SERVER_PRIVATE_KEY_FILE="${WG_CONFIG_DIR}/server_private.key"
SERVER_PUBLIC_KEY_FILE="${WG_CONFIG_DIR}/server_public.key"

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

# Создание конфигурации WireGuard
if [ ! -f "$WG_CONFIG_PATH" ]; then
    echo "Creating WireGuard configuration at $WG_CONFIG_PATH..."
    mkdir -p "$WG_CONFIG_DIR"
    cat <<EOF > "$WG_CONFIG_PATH"
[Interface]
Address = ${WG_DEFAULT_NETWORK}
PrivateKey = ${SERVER_PRIVATE_KEY}
ListenPort = ${WG_PORT}
DNS = ${WG_DNS}
SaveConfig = true

PostUp = iptables -t nat -A POSTROUTING -s ${WG_DEFAULT_NETWORK} -o eth0 -j MASQUERADE; \
         iptables -A INPUT -p udp -m udp --dport ${WG_PORT} -j ACCEPT; \
         iptables -A FORWARD -i ${WG_INTERFACE} -j ACCEPT; \
         iptables -A FORWARD -o ${WG_INTERFACE} -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -s ${WG_DEFAULT_NETWORK} -o eth0 -j MASQUERADE; \
           iptables -D INPUT -p udp -m udp --dport ${WG_PORT} -j ACCEPT; \
           iptables -D FORWARD -i ${WG_INTERFACE} -j ACCEPT; \
           iptables -D FORWARD -o ${WG_INTERFACE} -j ACCEPT
EOF
fi

chmod 600 "$WG_CONFIG_PATH"

# Запуск WireGuard
if ip link show "$WG_INTERFACE" &>/dev/null; then
    echo "WireGuard interface ${WG_INTERFACE} already exists. Skipping activation."
else
    wg-quick up "$WG_CONFIG_PATH"
fi

exec python3 app.py
