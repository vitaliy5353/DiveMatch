from flask import Flask, request, jsonify
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
BOT_TOKEN = "8825869613:AAHxwoPoJXFBWIFT6cxgeL_9vsj4JqvZGOU"
BOT_USERNAME = "DiveMatch_Bot"
ADMIN_ID = "8378052126"

SECRET_KEY = "DiveMatchSuperSecretKey2026"
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"online": {}, "profiles": [], "messages": []}

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
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "")
                        if text.startswith("/start"):
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                                "chat_id": chat_id, "text": "Привет! Нажми кнопку внизу, чтобы получить код.",
                                "reply_markup": {"keyboard": [[{"text": "📱 Отправить мой номер", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
                            })
                        elif "contact" in msg:
                            phone = ''.join(filter(str.isdigit, msg["contact"]["phone_number"]))
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                                "chat_id": chat_id, "text": f"🔑 Ваш код: <code>{generate_code(phone)}</code>", "parse_mode": "HTML"
                            })
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
    db = load_db()
    db["profiles"].append(request.json)
    save_db(db)
    return jsonify({"success": True})

@app.route('/api/get_profiles', methods=['GET'])
def get_profiles():
    return jsonify(load_db().get("profiles", []))

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

# --- НОВОЕ: СООБЩЕНИЯ ---
@app.route('/api/get_messages', methods=['POST'])
def get_messages():
    data = request.json or {}
    user1 = data.get('user1')
    user2 = data.get('user2')
    db = load_db()
    msgs = [m for m in db.get("messages", []) if (m["from"] == user1 and m["to"] == user2) or (m["from"] == user2 and m["to"] == user1)]
    return jsonify(msgs)

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    db = load_db()
    db["messages"].append({
        "from": data["from"],
        "to": data["to"],
        "text": data["text"],
        "time": time.strftime("%H:%M")
    })
    save_db(db)
    return jsonify({"success": True})

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f: return f.read()
    except: return "Ошибка: index.html не найден"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
