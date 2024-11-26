from flask import Flask, render_template, redirect, url_for, request, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import os
import subprocess
import json
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

WG_CONFIG_DIR = os.getenv("WG_CONFIG_DIR", "/etc/wireguard")
os.makedirs(WG_CONFIG_DIR, exist_ok=True)

USER_DATA_FILE = os.path.join(WG_CONFIG_DIR, "users.json")
WG_CONF_FILE = os.path.join(WG_CONFIG_DIR, "wg0.conf")

if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "w") as f:
        json.dump({}, f)

def load_user_data():
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

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

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user_data = load_user_data()
    return render_template("dashboard.html", user=current_user, users=user_data.items())

@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    username = request.form.get("username")
    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    try:
        client_private_key = subprocess.check_output([
            "docker", "exec", "wireguard", "wg", "genkey"
        ]).strip().decode("utf-8")
        client_public_key = subprocess.check_output([
            "docker", "exec", "wireguard", "bash", "-c",
            f"echo {client_private_key} | wg pubkey"
        ]).strip().decode("utf-8")

        server_url = os.getenv("SERVERURL")
        server_port = os.getenv("SERVERPORT")
        peer_dns = os.getenv("PEERDNS")
        allowed_ips = os.getenv("ALLOWEDIPS")
        internal_subnet = os.getenv("INTERNAL_SUBNET")

        if not all([server_url, server_port, peer_dns, allowed_ips]):
            return jsonify({"status": "error", "message": "Server configuration variables are missing"}), 500

        client_ip = f"{internal_subnet.rsplit('.', 1)[0]}.{len(load_user_data()) + 2}"

        subprocess.check_call([
            "docker", "exec", "wireguard", "bash", "-c",
            f"echo -e '\\n[Peer]\\nPublicKey = {client_public_key}\\nAllowedIPs = {client_ip}/32' >> {WG_CONF_FILE}"
        ])

        subprocess.check_call([
            "docker", "exec", "wireguard", "bash", "-c",
            f"wg syncconf wg0 <(wg-quick strip wg0)"
        ])

        client_config_path = os.path.join(WG_CONFIG_DIR, f"{username}.conf")
        server_public_key = subprocess.check_output([
            "docker", "exec", "wireguard", "bash", "-c",
            "cat /etc/wireguard/wg0.conf | grep PrivateKey | cut -d ' ' -f3 | wg pubkey"
        ]).strip().decode("utf-8")

        with open(client_config_path, "w") as f:
            f.write(f"""[Interface]
PrivateKey = {client_private_key}
Address = {client_ip}/24
DNS = {peer_dns}

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_url}:{server_port}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
""")        
        user_data = load_user_data()
        user_data[username] = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config_path": client_config_path,
            "active": True,
            "public_key": client_public_key,
            "ip": client_ip
        }
        save_user_data(user_data)

        return jsonify({"status": "success", "user": {username: user_data[username]}}), 200
    except subprocess.CalledProcessError as e:
        print(f"Error creating user {username}: {e}")
        return jsonify({"status": "error", "message": "Failed to create user"}), 500

@app.route("/download_config/<username>")
@login_required
def download_config(username):
    user_data = load_user_data()
    if username in user_data:
        config_path = user_data[username].get("config_path")
        if config_path and os.path.exists(config_path):
            return send_file(
                config_path,
                as_attachment=True,
                download_name=f"{username}.conf"
            )
    return "File not found", 404

@app.route("/delete_config/<username>", methods=["POST"])
@login_required
def delete_config(username):
    try:
        user_data = load_user_data()
        if username in user_data:
            config_path = user_data[username].get("config_path")
            if config_path and os.path.exists(config_path):
                os.remove(config_path)
            del user_data[username]
            save_user_data(user_data)
        return jsonify({"status": "success", "message": f"User {username} deleted successfully"}), 200
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Client not found"}), 404
    except subprocess.CalledProcessError as e:
        print(f"Error deleting user {username}: {e}")
        return jsonify({"status": "error", "message": "Failed to delete user"}), 500

@app.route("/toggle_user/<username>", methods=["POST"])
@login_required
def toggle_user(username):
    user_data = load_user_data()
    if username in user_data:
        current_status = user_data[username].get("active", True)
        user_data[username]["active"] = not current_status
        save_user_data(user_data)

        public_key = user_data[username]["public_key"]
        ip = user_data[username]["ip"]

        if user_data[username]["active"]:
            subprocess.check_call([
                "docker", "exec", "wireguard", "bash", "-c",
                f"iptables -D FORWARD -s {ip} -j DROP"
            ])
        else:
            subprocess.check_call([
                "docker", "exec", "wireguard", "bash", "-c",
                f"iptables -I FORWARD 1 -s {ip} -j DROP"
            ])

        return jsonify({"status": "success", "active": user_data[username]["active"]})
    return jsonify({"status": "error", "message": "User not found"}), 404

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=80)
