from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import random
import string

app = Flask(__name__)
CORS(app)

# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = "8825869613:AAHxwoPoJXFBWIFT6cxgeL_9vsj4JqvZGOU"  # <-- ЗАМЕНИ
ADMIN_ID = "8378052126"  # <-- ЗАМЕНИ

active_codes = {}

# --- БАЗА ДАННЫХ В ПАМЯТИ ---
online_users = set()  # Сюда записываются IP тех, кто зашел
profiles = []         # Сюда сохраняются анкеты

def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
        return True
    except Exception as e:
        print("Ошибка отправки в ТГ:", e)
        return False

@app.route('/api/request_code', methods=['POST'])
def request_code():
    data = request.json
    phone = data.get('phone')
    if not phone:
        return jsonify({"success": False, "message": "Нет номера"}), 400
    
    code = ''.join(random.choices(string.digits, k=5))
    active_codes[phone] = {"code": code, "used": False}
    
    msg = f"🔑 <b>Новый вход!</b>\nНомер: <code>{phone}</code>\nКод: <code>{code}</code>"
    send_telegram_msg(ADMIN_ID, msg)
    return jsonify({"success": True, "message": "Код отправлен"})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    user_code = data.get('code')
    
    # МАСТЕР-КОДЫ
    if user_code == "1" or user_code == "2":
        return jsonify({"success": True, "message": "Вход по мастер-коду"})
    
    if phone not in active_codes:
        return jsonify({"success": False, "message": "Код не запрашивался"}), 400
        
    saved_data = active_codes[phone]
    if saved_data['used']:
        return jsonify({"success": False, "message": "Код уже использован"}), 400
        
    if saved_data['code'] == user_code:
        active_codes[phone]['used'] = True
        return jsonify({"success": True, "message": "Успешный вход"})
    
    return jsonify({"success": False, "message": "Неверный код"}), 400

# --- СОХРАНЕНИЕ И ПОЛУЧЕНИЕ АНКЕТ ---
@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    profiles.append(data)
    return jsonify({"success": True})

@app.route('/api/get_profiles', methods=['GET'])
def get_profiles():
    return jsonify(profiles)

# --- ПОДСЧЕТ ОНЛАЙНА ---
@app.route('/api/online', methods=['GET'])
def get_online():
    # Если список пуст (например, после перезагрузки сервера), ставим минимум 1
    count = len(online_users) if len(online_users) > 0 else 1
    return jsonify({"count": count})

# --- ОТДАЧА САЙТА ---
@app.route('/')
def index():
    user_ip = request.remote_addr
    online_users.add(user_ip)
    
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Ошибка: файл index.html не найден!"

if __name__ == '__main__':
    print("Сервер запущен на http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000)
