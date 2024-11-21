from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import os
import subprocess
import json
from datetime import datetime
import ipaddress

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# WireGuard parameters
WG_CONFIG_DIR = os.getenv("WG_CONFIG_DIR", "/etc/wireguard")
WG_INTERFACE = os.getenv("WG_INTERFACE")
WG_PORT = os.getenv("WG_PORT")
WG_HOST = os.getenv("WG_HOST")
WG_DNS = os.getenv("WG_DNS")
WG_ALLOWED_IPS = os.getenv("WG_ALLOWED_IPS")
CLIENTS_DIR = os.path.join(WG_CONFIG_DIR, "clients")
USER_DATA_FILE = os.path.join(WG_CONFIG_DIR, "users.json")
SERVER_PRIVATE_KEY_FILE = os.path.join(WG_CONFIG_DIR, "server_private.key")
SERVER_PUBLIC_KEY_FILE = os.path.join(WG_CONFIG_DIR, "server_public.key")

os.makedirs(CLIENTS_DIR, exist_ok=True)
if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "w") as f:
        json.dump({}, f)

# Generate server keys if not present
if not os.path.exists(SERVER_PRIVATE_KEY_FILE):
    private_key = subprocess.check_output(["wg", "genkey"]).decode("utf-8").strip()
    with open(SERVER_PRIVATE_KEY_FILE, "w") as f:
        f.write(private_key)
    os.chmod(SERVER_PRIVATE_KEY_FILE, 0o600)

if not os.path.exists(SERVER_PUBLIC_KEY_FILE):
    private_key = open(SERVER_PRIVATE_KEY_FILE).read().strip()
    public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode("utf-8")).decode("utf-8").strip()
    with open(SERVER_PUBLIC_KEY_FILE, "w") as f:
        f.write(public_key)

# Load user data
def load_user_data():
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

# Save user data
def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Get next available client IP
def get_next_client_address(server_address):
    user_data = load_user_data()
    existing_addresses = {user["address"].split("/")[0] for user in user_data.values()}
    network = ipaddress.ip_network(server_address, strict=False)
    for ip in network.hosts():
        if str(ip) not in existing_addresses:
            return f"{ip}/32"
    raise ValueError("No available IPs!")

# Get server information
def get_server_info():
    config_path = os.path.join(WG_CONFIG_DIR, f"{WG_INTERFACE}.conf")
    server_info = {
        "Address": WG_HOST,
        "Port": WG_PORT,
        "DNS": WG_DNS,
        "AllowedIPs": WG_ALLOWED_IPS,
        "PublicKey": open(SERVER_PUBLIC_KEY_FILE).read().strip(),
    }
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("Address"):
                    server_info["Address"] = line.split("=")[1].strip()
                elif line.startswith("DNS"):
                    server_info["DNS"] = line.split("=")[1].strip()
                elif line.startswith("AllowedIPs"):
                    server_info["AllowedIPs"] = line.split("=")[1].strip()
    return server_info

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("FLASK_LOGIN_PASSWORD"):
            user = User(id=1)
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid password")
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    user_data = load_user_data()
    server_info = get_server_info()
    return render_template("dashboard.html", users=user_data.items(), server_info=server_info)

@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    username = request.form.get("username")
    if not username:
        return jsonify({"status": "error", "message": "Invalid username"}), 400
    user_data = load_user_data()
    if username in user_data:
        return jsonify({"status": "error", "message": "User already exists"}), 400
    private_key = subprocess.check_output(["wg", "genkey"]).decode("utf-8").strip()
    public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode("utf-8")).decode("utf-8").strip()
    preshared_key = subprocess.check_output(["wg", "genpsk"]).decode("utf-8").strip()
    server_info = get_server_info()
    client_address = get_next_client_address(server_info["Address"])
    client_config = f"""
[Interface]
PrivateKey = {private_key}
Address = {client_address}
DNS = {server_info['DNS']}

[Peer]
PublicKey = {server_info['PublicKey']}
PresharedKey = {preshared_key}
Endpoint = {server_info['Address']}:{server_info['Port']}
AllowedIPs = {server_info['AllowedIPs']}
PersistentKeepalive = 25
"""
    user_data[username] = {"address": client_address, "created_at": str(datetime.now())}
    save_user_data(user_data)
    user_config_path = os.path.join(CLIENTS_DIR, f"{username}.conf")
    with open(user_config_path, "w") as f:
        f.write(client_config)
    return jsonify({"status": "success", "config": client_config})

@app.route("/download_config/<username>")
@login_required
def download_config(username):
    user_data = load_user_data()
    if username not in user_data:
        return "Config file not found", 404
    config_path = os.path.join(CLIENTS_DIR, f"{username}.conf")
    if os.path.exists(config_path):
        return send_file(config_path, as_attachment=True)
    return "Config file not found", 404

@app.route("/delete_user/<username>", methods=["POST"])
@login_required
def delete_user(username):
    user_data = load_user_data()
    if username not in user_data:
        return jsonify({"status": "error", "message": "User not found"}), 404
    user_config_path = os.path.join(CLIENTS_DIR, f"{username}.conf")
    if os.path.exists(user_config_path):
        os.remove(user_config_path)
    del user_data[username]
    save_user_data(user_data)
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=80)
