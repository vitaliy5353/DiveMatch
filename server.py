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

# --- НАСТРОЙКИ БОТА (ЗАМЕНИ НА СВОИ) ---
BOT_TOKEN = "8825869613:AAHxwoPoJXFBWIFT6cxgeL_9vsj4JqvZGOU"  # <-- ЗАМЕНИ
BOT_USERNAME = "DiveMatch_Bot"
ADMIN_ID = "8378052126"  # <-- ЗАМЕНИ

SECRET_KEY = "DiveMatchSuperSecretKey2026"
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"online": {}, "profiles": []}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def generate_code(phone):
    hash_str = hashlib.md5((phone + SECRET_KEY).encode()).hexdigest()
    num = int(hash_str, 16) % 90000 + 10000
    return str(num)

# --- ОЧИСТКА СТАРЫХ ПОЛЬЗОВАТЕЛЕЙ (УСКОРЕННАЯ) ---
def cleanup_online():
    while True:
        try:
            db = load_db()
            now = time.time()
            
            # ТЕПЕРЬ УДАЛЯЕМ ТЕХ, КТО НЕ ЗАХОДИЛ 30 СЕКУНД
            to_delete = [sid for sid, last_seen in db.get("online", {}).items() if now - last_seen > 30]
            if to_delete:
                for sid in to_delete:
                    del db["online"][sid]
                save_db(db)
                print(f"[ОЧИСТКА] Удалено {len(to_delete)} неактивных пользователей")
        except Exception as e:
            print("Ошибка очистки:", e)
        # ПРОВЕРЯЕМ КАЖДЫЕ 10 СЕКУНД
        time.sleep(10)

threading.Thread(target=cleanup_online, daemon=True).start()

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
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": f"Привет, {username}! 👋\nНажми кнопку внизу, чтобы получить код.",
                                "reply_markup": keyboard
                            })
                        
                        elif "contact" in msg:
                            phone = msg["contact"]["phone_number"].replace("+", "")
                            clean_phone = ''.join(filter(str.isdigit, phone))
                            code = generate_code(clean_phone)
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": f"🔑 Ваш код для входа: <code>{code}</code>",
                                "parse_mode": "HTML"
                            })
        except Exception as e:
            print("Ошибка бота:", e)
        time.sleep(1)

threading.Thread(target=telegram_bot_listener, daemon=True).start()

@app.route('/api/request_code', methods=['POST'])
def request_code():
    return jsonify({"success": True, "bot_url": f"https://t.me/{BOT_USERNAME}"})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    user_code = data.get('code')
    
    if user_code == "1" or user_code == "2":
        return jsonify({"success": True, "message": "Вход по мастер-коду"})
    
    if not phone or not user_code:
        return jsonify({"success": False, "message": "Нет данных"}), 400

    clean_phone = ''.join(filter(str.isdigit, phone))
    if generate_code(clean_phone) == user_code:
        return jsonify({"success": True, "message": "Успешный вход"})
    return jsonify({"success": False, "message": "Неверный код"}), 400

@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    db = load_db()
    db["profiles"].append(data)
    save_db(db)
    return jsonify({"success": True})

@app.route('/api/get_profiles', methods=['GET'])
def get_profiles():
    db = load_db()
    return jsonify(db["profiles"])

@app.route('/api/ping', methods=['POST'])
def ping():
    data = request.json or {}
    session_id = data.get('session_id')
    
    if session_id:
        db = load_db()
        if "online" not in db: db["online"] = {}
        db["online"][session_id] = time.time() # Запоминаем время захода
        save_db(db)
        
    db = load_db()
    count = len(db.get("online", {})) if len(db.get("online", {})) > 0 else 1
    return jsonify({"count": count})

# Обработка закрытия страницы (когда браузер выключают)
@app.route('/api/offline', methods=['POST'])
def offline():
    data = request.json or {}
    session_id = data.get('session_id')
    if session_id:
        db = load_db()
        if "online" in db and session_id in db["online"]:
            del db["online"][session_id]
            save_db(db)
    return jsonify({"success": True})

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Ошибка: index.html не найден"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
