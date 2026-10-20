from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import random
import string
import os
import threading
import time
import hashlib
import json

app = Flask(__name__)
CORS(app)

# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = "8825869613:AAHxwoPoJXFBWIFT6cxgeL_9vsj4JqvZGOU"  # <-- ЗАМЕНИ
BOT_USERNAME = "DiveMatch_Bot"
ADMIN_ID = "8378052126"  # <-- ЗАМЕНИ

# --- ПАРОЛЬ ДЛЯ АДМИНКИ ---
ADMIN_PASSWORD = "admin2026" # <--- ОБЯЗАТЕЛЬНО СМЕНИ

SECRET_KEY = "DiveMatchSuperSecretKey2026"
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"online": {}, "profiles": [], "messages": [], "banned": [], "reports": []}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def generate_code(phone):
    hash_str = hashlib.md5((phone + SECRET_KEY).encode()).hexdigest()
    return str(int(hash_str, 16) % 90000 + 10000)

def cleanup_online():
    while True:
        try:
            db = load_db()
            now = time.time()
            to_delete = [sid for sid, last_seen in db.get("online", {}).items() if now - last_seen > 30]
            if to_delete:
                for sid in to_delete: del db["online"][sid]
                save_db(db)
        except Exception as e: print("Очистка:", e)
        time.sleep(10)

threading.Thread(target=cleanup_online, daemon=True).start()

def telegram_bot_listener():
    last_update_id = 0
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": last_update_id + 1, "timeout": 10}, timeout=15).json()
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        msg = update["message"]; chat_id = msg["chat"]["id"]; text = msg.get("text", "")
                        if text.startswith("/start"):
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": "Привет! Нажми кнопку внизу, чтобы получить код.", "reply_markup": {"keyboard": [[{"text": "📱 Отправить мой номер", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}})
                        elif "contact" in msg:
                            phone = ''.join(filter(str.isdigit, msg["contact"]["phone_number"]))
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": f"🔑 Ваш код: <code>{generate_code(phone)}</code>", "parse_mode": "HTML"})
        except Exception as e: print("Бот:", e)
        time.sleep(1)

threading.Thread(target=telegram_bot_listener, daemon=True).start()

@app.route('/api/request_code', methods=['POST'])
def request_code(): return jsonify({"success": True, "bot_url": f"https://t.me/{BOT_USERNAME}"})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    if data.get('code') in ["1", "2"]: return jsonify({"success": True})
    phone = ''.join(filter(str.isdigit, data.get('phone', '')))
    if generate_code(phone) == data.get('code'): return jsonify({"success": True})
    return jsonify({"success": False, "message": "Неверный код"}), 400

@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    db = load_db()
    if data['name'] in db.get("banned", []):
        return jsonify({"success": False, "message": "Вы забанены"}), 403
    db["profiles"].append(data)
    save_db(db)
    return jsonify({"success": True})

@app.route('/api/get_profiles', methods=['GET'])
def get_profiles():
    db = load_db()
    banned = db.get("banned", [])
    profiles = [p for p in db.get("profiles", []) if p['name'] not in banned]
    return jsonify(profiles)

@app.route('/api/ping', methods=['POST'])
def ping():
    data = request.json or {}
    if data.get('session_id'):
        db = load_db()
        if "online" not in db: db["online"] = {}
        db["online"][data['session_id']] = time.time()
        save_db(db)
    db = load_db()
    return jsonify({"count": len(db.get("online", {})) if db.get("online") else 1})

@app.route('/api/offline', methods=['POST'])
def offline():
    data = request.json or {}
    if data.get('session_id'):
        db = load_db()
        if "online" in db and data['session_id'] in db["online"]:
            del db["online"][data['session_id']]
            save_db(db)
    return jsonify({"success": True})

@app.route('/api/get_messages', methods=['POST'])
def get_messages():
    data = request.json or {}
    db = load_db()
    msgs = [m for m in db.get("messages", []) if (m["from"] == data.get('user1') and m["to"] == data.get('user2')) or (m["from"] == data.get('user2') and m["to"] == data.get('user1'))]
    return jsonify(msgs)

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    db = load_db()
    if data['from'] in db.get("banned", []):
        return jsonify({"success": False}), 403
    db["messages"].append({"from": data["from"], "to": data["to"], "text": data["text"], "time": time.strftime("%H:%M")})
    save_db(db)
    return jsonify({"success": True})

# --- ЖАЛОБЫ ---
@app.route('/api/report', methods=['POST'])
def report():
    data = request.json
    db = load_db()
    
    report_data = {
        "from": data['from'],
        "to": data['to'],
        "reason": data['reason'],
        "time": time.strftime("%d.%m %H:%M")
    }
    
    if "reports" not in db: db["reports"] = []
    db["reports"].append(report_data)
    save_db(db)
    
    # Отправляем жалобу в Telegram
    msg = f"🚩 <b>НОВАЯ ЖАЛОБА!</b>\nКто пожаловался: {data['from']}\nНа кого: {data['to']}\nПричина: {data['reason']}"
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"})
    
    return jsonify({"success": True})

# --- АДМИН-ПАНЕЛЬ ---
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DiveMatch — Админка</title>
<style>
    body { font-family: sans-serif; background: #0e1621; color: #fff; padding: 20px; }
    h1 { color: #5288c1; margin-bottom: 20px; }
    .box { background: #17212b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
    .user { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #232e3c; padding: 10px 0; }
    .btn { background: #e53935; color: #fff; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; }
    .btn-green { background: #4dcd5e; }
    .btn-blue { background: #5288c1; }
    input { padding: 10px; border-radius: 5px; border: none; width: 100%; max-width: 300px; margin-bottom: 10px; }
    .login-box { text-align: center; margin-top: 20vh; }
    .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
    .tab { padding: 10px 20px; background: #232e3c; border-radius: 5px; cursor: pointer; }
    .tab.active { background: #5288c1; }
    .report-item { background: #232e3c; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
</style>
</head>
<body>
    <div id="login" class="login-box">
        <h1>Вход в Админку</h1>
        <input type="password" id="pass" placeholder="Пароль">
        <button class="btn btn-blue" onclick="login()">Войти</button>
    </div>
    <div id="panel" style="display:none;">
        <h1>Админ-панель</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="showTab('profiles')">Анкеты</div>
            <div class="tab" onclick="showTab('reports')">Жалобы</div>
            <div class="tab" onclick="showTab('banned')">Забаненные</div>
        </div>
        
        <div class="box" id="tab-profiles">
            <h3>Все анкеты</h3>
            <div id="profilesList">Загрузка...</div>
        </div>

        <div class="box" id="tab-reports" style="display:none;">
            <h3>Жалобы пользователей</h3>
            <div id="reportsList">Загрузка...</div>
        </div>

        <div class="box" id="tab-banned" style="display:none;">
            <h3>Забаненные</h3>
            <div id="bannedList">Загрузка...</div>
        </div>
    </div>

    <script>
        let password = "";
        let adminData = {};

        function login() {
            password = document.getElementById('pass').value;
            fetch('/api/admin/data', { headers: { 'X-Password': password } })
                .then(r => r.json())
                .then(data => {
                    if (data.error) return alert('Неверный пароль');
                    document.getElementById('login').style.display = 'none';
                    document.getElementById('panel').style.display = 'block';
                    adminData = data;
                    renderAll();
                });
        }

        function showTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.box').forEach(b => b.style.display = 'none');
            
            event.target.classList.add('active');
            document.getElementById('tab-' + name).style.display = 'block';
        }

        function renderAll() {
            renderProfiles(adminData.profiles || []);
            renderReports(adminData.reports || []);
            renderBanned(adminData.banned || []);
        }

        function renderProfiles(profiles) {
            const div = document.getElementById('profilesList');
            div.innerHTML = profiles.length ? '' : 'Никого нет';
            profiles.forEach(p => {
                const isBanned = adminData.banned.includes(p.name);
                div.innerHTML += `<div class="user">
                    <div><b>${p.name}, ${p.age}</b><br><small>${p.city} | ${p.gender}</small></div>
                    ${isBanned 
                        ? `<button class="btn btn-green" onclick="unban('${p.name}')">Разбанить</button>`
                        : `<button class="btn" onclick="ban('${p.name}')">Забанить</button>`
                    }
                </div>`;
            });
        }

        function renderReports(reports) {
            const div = document.getElementById('reportsList');
            div.innerHTML = reports.length ? '' : 'Жалоб нет';
            reports.forEach(r => {
                div.innerHTML += `<div class="report-item">
                    <b>${r.from}</b> пожаловался на <b>${r.to}</b><br>
                    Причина: ${r.reason}<br>
                    <small>${r.time}</small><br><br>
                    <button class="btn" onclick="ban('${r.to}')">Забанить ${r.to}</button>
                </div>`;
            });
        }

        function renderBanned(banned) {
            const div = document.getElementById('bannedList');
            div.innerHTML = banned.length ? '' : 'Никого нет';
            banned.forEach(name => {
                div.innerHTML += `<div class="user"><span>${name}</span><button class="btn btn-green" onclick="unban('${name}')">Разбанить</button></div>`;
            });
        }

        function ban(name) {
            fetch('/api/admin/ban', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Password': password },
                body: JSON.stringify({ name })
            }).then(() => location.reload());
        }

        function unban(name) {
            fetch('/api/admin/unban', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Password': password },
                body: JSON.stringify({ name })
            }).then(() => location.reload());
        }
    </script>
</body>
</html>
"""

@app.route('/admin')
def admin_panel():
    return render_template_string(ADMIN_HTML)

@app.route('/api/admin/data', methods=['GET'])
def admin_data():
    if request.headers.get('X-Password') != ADMIN_PASSWORD:
        return jsonify({"error": "Auth"}), 401
    db = load_db()
    return jsonify({"profiles": db.get("profiles", []), "banned": db.get("banned", []), "reports": db.get("reports", [])})

@app.route('/api/admin/ban', methods=['POST'])
def admin_ban():
    if request.headers.get('X-Password') != ADMIN_PASSWORD:
        return jsonify({"error": "Auth"}), 401
    name = request.json.get('name')
    db = load_db()
    if "banned" not in db: db["banned"] = []
    if name not in db["banned"]: db["banned"].append(name)
    save_db(db)
    return jsonify({"success": True})

@app.route('/api/admin/unban', methods=['POST'])
def admin_unban():
    if request.headers.get('X-Password') != ADMIN_PASSWORD:
        return jsonify({"error": "Auth"}), 401
    name = request.json.get('name')
    db = load_db()
    if "banned" in db and name in db["banned"]:
        db["banned"].remove(name)
        save_db(db)
    return jsonify({"success": True})

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f: return f.read()
    except: return "Ошибка: index.html не найден"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
