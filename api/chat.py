# --- chat.py (версия с google-genai) ---

import os
import base64
import re
import json
import logging
import requests
import redis

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from PIL import Image
import io

# --- Базовая настройка ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

CORS(app, resources={
    r"/api/*": {
        "origins": [frontend_url]
    }
})

# --- Redis ---
redis_client = None
redis_url = os.getenv('REDIS_URL')

if redis_url:
    try:
        redis_client = redis.from_url(redis_url, decode_responses=False)
        redis_client.ping()
        logging.info("Подключение к Redis успешно.")
    except Exception as e:
        logging.error(f"Ошибка подключения к Redis: {e}")
        redis_client = None
else:
    logging.warning("REDIS_URL не задан. Память будет временной.")

# --- Gemini (google-genai) с вашим ключом ---
gemini_api_key = "AIzaSyAkNugx2y8cwtbyf_NKjzR6bdZ7ZFdF6l4"  # Ваш ключ
if not gemini_api_key: 
    raise ValueError("Не задан GEMINI_API_KEY")

client = genai.Client(api_key=gemini_api_key)

# --- Azure Speech ---
speech_key = os.getenv("SPEECH_KEY")
speech_region = os.getenv("SPEECH_REGION")

if not (speech_key and speech_region):
    logging.warning("Azure Speech отключён.")

# --- Системная инструкция ---
SYSTEM_INSTRUCTION = """
Ты ИИ-друг для детей 8–12 лет.
Отвечай коротко (до 100 слов), тепло и позитивно.
Поддерживай ребёнка и задавай вопросы.
Используй эмодзи ✨🚀🎨🌟
"""

# --- Очистка текста ---
def cleanup_text_for_speech(text):
    """Очищает текст от специальных символов для синтеза речи"""
    if not text:
        return ""
    pattern = re.compile(r'[^a-zA-Zа-яА-Я0-9,.?!\s]')
    return re.sub(pattern, '', text).strip()

# --- Валидация истории чата ---
def validate_history(history):
    """Проверяет корректность структуры истории чата"""
    if not isinstance(history, list):
        return False, "history должен быть списком"
    
    for msg in history:
        if not isinstance(msg, dict):
            return False, "Каждое сообщение должно быть словарем"
        if "role" not in msg:
            return False, "Каждое сообщение должно содержать поле 'role'"
        if msg["role"] not in ["user", "model"]:
            return False, "role должен быть 'user' или 'model'"
    
    return True, "OK"

# --- CHAT API ---
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Обрабатывает запросы к чату с потоковой передачей ответов
    Ожидает JSON с полем "history"
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Тело запроса не может быть пустым"}), 400
            
        history = data.get("history", [])

        # Валидация истории
        is_valid, error_message = validate_history(history)
        if not is_valid:
            return jsonify({"error": error_message}), 400

        # Формируем сообщения для Gemini
        messages = []

        # Добавляем системную инструкцию
        messages.append({
            "role": "user",
            "parts": [SYSTEM_INSTRUCTION]
        })

        # Добавляем историю чата
        for msg in history:
            role = "model" if msg["role"] == "model" else "user"
            messages.append({
                "role": role,
                "parts": msg.get("parts", [msg.get("content", "")])
            })

        def generate():
            """Генератор для потоковой передачи ответа"""
            try:
                response = client.models.generate_content_stream(
                    model="gemini-2.0-flash",
                    contents=messages
                )

                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                logging.error(f"Ошибка при генерации ответа: {e}")
                yield "Извините, произошла ошибка при генерации ответа."

        return Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')

    except Exception as e:
        logging.error(f"Ошибка /api/chat: {e}", exc_info=True)
        return Response("Внутренняя ошибка сервера", status=500)

# --- SPEECH API ---
@app.route('/api/speech', methods=['POST'])
def speech():
    """
    Преобразует текст в речь с использованием Azure Speech Services
    Ожидает JSON с полем "text"
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Тело запроса не может быть пустым"}), 400
            
        text = data.get("text")

        if not text:
            return jsonify({"error": "text обязателен"}), 400

        text_clean = cleanup_text_for_speech(text)

        if not (speech_key and speech_region):
            return jsonify({"error": "Azure Speech не настроен"}), 500

        voice_name = os.getenv("AZURE_VOICE_NAME", "ru-RU-DmitryNeural")
        
        ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ru-RU'>
            <voice name='{voice_name}'>{text_clean}</voice>
        </speak>
        """

        endpoint = f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"

        headers = {
            "Ocp-Apim-Subscription-Key": speech_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
            "User-Agent": "KidsAI"
        }

        # Добавляем таймаут для запроса
        response = requests.post(
            endpoint, 
            data=ssml.encode('utf-8'), 
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        audio_base64 = base64.b64encode(response.content).decode('utf-8')

        return jsonify({
            "audio_base64": audio_base64,
            "success": True
        })

    except requests.exceptions.Timeout:
        logging.error("Таймаут при запросе к Azure Speech")
        return jsonify({"error": "Таймаут сервиса речи"}), 504
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка запроса к Azure Speech: {e}")
        return jsonify({"error": "Ошибка сервиса речи"}), 502
    except Exception as e:
        logging.error(f"Ошибка /api/speech: {e}", exc_info=True)
        return Response("Внутренняя ошибка сервера", status=500)

# --- Health check endpoint ---
@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({
        "status": "healthy",
        "gemini_configured": bool(gemini_api_key),
        "azure_speech_configured": bool(speech_key and speech_region),
        "redis_configured": redis_client is not None
    })

# --- Запуск ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)