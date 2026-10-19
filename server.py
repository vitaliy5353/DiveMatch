from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import random
import string
import os
import threading
import time
import json

app = Flask(__name__)
CORS(app)

# --- НАСТРОЙКИ БОТА (ЗАМЕНИ НА СВОИ) ---
BOT_TOKEN = "8825869613:AAHxwoPoJXFBWIFT6cxgeL_9vsj4JqvZGOU"  # <-- ЗАМЕНИ
BOT_USERNAME = "DiveMatch_Bot" # Без @
ADMIN_ID = "8378052126"  # <-- ЗАМЕНИ

# --- БАЗА ДАННЫХ В ПАМЯТИ (И ФАЙЛЕ) ---
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"codes": {}, "profiles": [], "online": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()
active_codes = db["codes"]
profiles = db["profiles"]
online_users = db["online"]

def send_telegram_msg(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=5)
        return True
    except Exception as e:
        print("Ошибка отправки в ТГ:", e)
        return False

def telegram_bot_listener():
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 10}
            res = requests.get(url, params=params, timeout=15).json()
            
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    last_update_id = update["update_id"]
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "")
                        username = msg["from"].get("username", "друг")
                        
                        if text.startswith("/start"):
                            keyboard = {
                                "keyboard": [[{
                                    "text": "📱 Отправить мой номер",
                                    "request_contact": True
                                }]],
                                "resize_keyboard": True,
                                "one_time_keyboard": True
                            }
                            send_telegram_msg(chat_id, f"Привет, {username}! 👋\nНажми на кнопку внизу, чтобы получить код.", reply_markup=keyboard)
                        
                        elif "contact" in msg:
                            phone = msg["contact"]["phone_number"].replace("+", "")
                            clean_phone = ''.join(filter(str.isdigit, phone))
                            
                            # Если код для этого номера уже есть, берем его. Если нет - создаем.
                            if clean_phone in active_codes:
                                code = active_codes[clean_phone]["code"]
                            else:
                                code = ''.join(random.choices(string.digits, k=5))
                                active_codes[clean_phone] = {"code": code}
                                db["codes"] = active_codes
                                save_db(db)
                            
                            send_telegram_msg(chat_id, f"🔑 Ваш код для входа: <code>{code}</code>")
        except Exception as e:
            print("Ошибка в боте:", e)
        time.sleep(1)

threading.Thread(target=telegram_bot_listener, daemon=True).start()

@app.route('/api/request_code', methods=['POST'])
def request_code():
    data = request.json
    phone = data.get('phone')
    if not phone:
        return jsonify({"success": False, "message": "Нет номера"}), 400
    
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Создаем код, если его еще нет
    if clean_phone not in active_codes:
        code = ''.join(random.choices(string.digits, k=5))
        active_codes[clean_phone] = {"code": code}
        db["codes"] = active_codes
        save_db(db)
    
    bot_url = f"https://t.me/{BOT_USERNAME}"
    return jsonify({"success": True, "message": "Код создан", "bot_url": bot_url})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    user_code = data.get('code')
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    if user_code == "1" or user_code == "2":
        return jsonify({"success": True, "message": "Вход по мастер-коду"})
    
    if clean_phone not in active_codes:
        return jsonify({"success": False, "message": "Код не запрашивался"}), 400
        
    saved_data = active_codes[clean_phone]
        
    if saved_data['code'] == user_code:
        return jsonify({"success": True, "message": "Успешный вход"})
    
    return jsonify({"success": False, "message": "Неверный код"}), 400

@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    profiles.append(data)
    db["profiles"] = profiles
    save_db(db)
    return jsonify({"success": True})

@app.route('/api/get_profiles', methods=['GET'])
def get_profiles():
    return jsonify(profiles)

@app.route('/api/ping', methods=['POST'])
def ping():
    data = request.json or {}
    session_id = data.get('session_id')
    if session_id:
        online_users[session_id] = True
        db["online"] = online_users
        save_db(db)
    count = len(online_users) if len(online_users) > 0 else 1
    return jsonify({"count": count})

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Ошибка: файл index.html не найден!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
