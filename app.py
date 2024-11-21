from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import os
import subprocess
import json
from datetime import datetime
import ipaddress

# Загрузка переменных из .env файла
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Mock user for authentication
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Параметры WireGuard
WG_CONFIG_DIR = os.getenv("WG_CONFIG_DIR", "/etc/wireguard")
WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")
USER_DATA_FILE = os.path.join(WG_CONFIG_DIR, "users.json")
SERVER_PRIVATE_KEY_FILE = os.path.join(WG_CONFIG_DIR, "server_private.key")
SERVER_PUBLIC_KEY_FILE = os.path.join(WG_CONFIG_DIR, "server_public.key")

CLIENTS_DIR = os.path.join(WG_CONFIG_DIR, "clients")
os.makedirs(CLIENTS_DIR, exist_ok=True)

if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "w") as f:
        json.dump({}, f)

# Создание ключей, если их нет
if not os.path.exists(SERVER_PRIVATE_KEY_FILE):
    private_key = subprocess.check_output(["wg", "genkey"]).decode("utf-8").strip()
    with open(SERVER_PRIVATE_KEY_FILE, "w") as f:
        f.write(private_key)
    os.chmod(SERVER_PRIVATE_KEY_FILE, 0o600)

if not os.path.exists(SERVER_PUBLIC_KEY_FILE):
    with open(SERVER_PRIVATE_KEY_FILE, "r") as f:
        private_key = f.read().strip()
    public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode("utf-8")).decode("utf-8").strip()
    with open(SERVER_PUBLIC_KEY_FILE, "w") as f:
        f.write(public_key)

def load_user_data():
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_server_info():
    """Считывание текущей конфигурации WireGuard."""
    try:
        config_path = os.path.join(WG_CONFIG_DIR, f"{WG_INTERFACE}.conf")
        server_info = {
            "interface": WG_INTERFACE,
            "config_path": config_path,
            "private_key": open(SERVER_PRIVATE_KEY_FILE, "r").read().strip(),
            "public_key": open(SERVER_PUBLIC_KEY_FILE, "r").read().strip(),
        }

        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("Address"):
                    server_info["address"] = line.split("=")[1].strip()
                elif line.startswith("ListenPort"):
                    server_info["port"] = line.split("=")[1].strip()
                elif line.startswith("DNS"):
                    server_info["dns"] = line.split("=")[1].strip()
                elif line.startswith("AllowedIPs"):
                    server_info["allowed_ips"] = line.split("=")[1].strip()

        # Дополнительно считываем IP сервера для клиентов
        server_info["host"] = os.getenv("WG_HOST", server_info["address"].split("/")[0])

        return server_info
    except Exception as e:
        print(f"Error reading server info: {e}")
        return None

def get_next_client_address():
    """Генерация следующего доступного IP-адреса для клиента."""
    user_data = load_user_data()
    existing_addresses = {
        user_data[username].get("address").split("/")[0]
        for username in user_data if "address" in user_data[username]
    }
    network = ipaddress.ip_network(get_server_info()["address"], strict=False)
    for ip in network.hosts():
        candidate = str(ip)
        if candidate not in existing_addresses and candidate != network.network_address:
            return f"{candidate}/32"
    raise ValueError("Нет доступных IP-адресов в подсети!")

@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    username = request.form.get("username")
    if username:
        user_data = load_user_data()
        if username in user_data:
            return jsonify({"status": "error", "message": "User already exists"}), 400

        private_key = subprocess.check_output(["wg", "genkey"]).decode("utf-8").strip()
        public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode("utf-8")).decode("utf-8").strip()
        preshared_key = subprocess.check_output(["wg", "genpsk"]).decode("utf-8").strip()

        server_info = get_server_info()
        if not server_info:
            return jsonify({"status": "error", "message": "Server not configured"}), 500

        client_address = get_next_client_address()

        client_config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_address}
DNS = {server_info['dns']}

[Peer]
PublicKey = {server_info['public_key']}
PresharedKey = {preshared_key}
Endpoint = {server_info['host']}:{server_info['port']}
AllowedIPs = {server_info['allowed_ips']}
PersistentKeepalive = 25
"""

        user_config_path = os.path.join(CLIENTS_DIR, f"{username}.conf")
        with open(user_config_path, "w") as f:
            f.write(client_config)

        user_data[username] = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config_path": user_config_path,
            "address": client_address,
            "public_key": public_key,
            "preshared_key": preshared_key,
            "active": True
        }
        save_user_data(user_data)

        return jsonify({"status": "success", "user": (username, user_data[username])})
    return jsonify({"status": "error", "message": "Invalid username"}), 400

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=80)
