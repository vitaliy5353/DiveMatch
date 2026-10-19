from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import random
import string
import os
import threading
import time

app = Flask(__name__)
CORS(app)

# --- НАСТРОЙКИ БОТА (ЗАМЕНИ НА СВОИ) ---
BOT_TOKEN = "8825869613:AAHxwoPoJXFBWIFT6cxgeL_9vsj4JqvZGOU"  # <-- ЗАМЕНИ
BOT_USERNAME = "DiveMatch_Bot" # Без @
ADMIN_ID = "8378052126"  # <-- ЗАМЕНИ

active_codes = {}
online_users = {}
profiles = []

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

# --- ФОНОВЫЙ ПРОЦЕСС БОТА (СЛУШАЕТ СООБЩЕНИЯ) ---
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
                        
                        # 1. Если написали /start
                        if text.startswith("/start"):
                            keyboard = {
                                "keyboard": [[{
                                    "text": "📱 Отправить мой номер",
                                    "request_contact": True
                                }]],
                                "resize_keyboard": True,
                                "one_time_keyboard": True
                            }
                            send_telegram_msg(chat_id, f"Привет, {username}! 👋\nНажми на кнопку внизу, чтобы отправить свой номер и получить код для входа на сайт DiveMatch.", reply_markup=keyboard)
                        
                        # 2. Если прислали контакт
                        elif "contact" in msg:
                            phone = msg["contact"]["phone_number"].replace("+", "")
                            clean_phone = ''.join(filter(str.isdigit, phone))
                            
                            # Генерируем код и сохраняем
                            code = ''.join(random.choices(string.digits, k=5))
                            active_codes[clean_phone] = {"code": code, "used": False, "tg_id": chat_id}
                            
                            send_telegram_msg(chat_id, f"🔑 Ваш код для входа: <code>{code}</code>")
        except Exception as e:
            print("Ошибка в боте:", e)
        time.sleep(1)

# Запускаем бота в фоне
threading.Thread(target=telegram_bot_listener, daemon=True).start()

# --- API САЙТА ---
@app.route('/api/request_code', methods=['POST'])
def request_code():
    data = request.json
    phone = data.get('phone')
    if not phone:
        return jsonify({"success": False, "message": "Нет номера"}), 400
    
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Если кода еще нет в базе, создаем его
    if clean_phone not in active_codes:
        code = ''.join(random.choices(string.digits, k=5))
        active_codes[clean_phone] = {"code": code, "used": False, "tg_id": None}
    
    bot_url = f"https://t.me/{BOT_USERNAME}"
    return jsonify({"success": True, "message": "Код создан", "bot_url": bot_url})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    user_code = data.get('code')
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Мастер-коды
    if user_code == "1" or user_code == "2":
        return jsonify({"success": True, "message": "Вход по мастер-коду"})
    
    if clean_phone not in active_codes:
        return jsonify({"success": False, "message": "Код не запрашивался"}), 400
        
    saved_data = active_codes[clean_phone]
    if saved_data['used']:
        return jsonify({"success": False, "message": "Код уже использован"}), 400
        
    if saved_data['code'] == user_code:
        active_codes[clean_phone]['used'] = True
        return jsonify({"success": True, "message": "Успешный вход"})
    
    return jsonify({"success": False, "message": "Неверный код"}), 400

@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    profiles.append(data)
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
