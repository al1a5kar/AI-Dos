# --- chat.py (с улучшенным логированием для Gemini) ---

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
from PIL import Image
import google.generativeai as genai
import io

# --- Базовая настройка с ДЕТАЛЬНЫМ логированием ---
load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,  # Изменено с INFO на DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Настройка CORS для GitHub Pages ---
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

github_pages_url = os.getenv("GITHUB_PAGES_URL", "https://al1a5kar.github.io")
if github_pages_url not in allowed_origins:
    allowed_origins.append(github_pages_url)

CORS(app, resources={
    r"/api/*": {
        "origins": allowed_origins,
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "OPTIONS"]
    }
})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# --- Redis ---
redis_client = None
redis_url = os.getenv('REDIS_URL')

if redis_url:
    try:
        redis_client = redis.from_url(redis_url, decode_responses=False)
        redis_client.ping()
        logger.info("Подключение к Redis успешно.")
    except Exception as e:
        logger.error(f"Ошибка подключения к Redis: {e}")
        redis_client = None
else:
    logger.warning("REDIS_URL не задан. Память будет временной.")

# --- Gemini (google-genai) с вашим ключом ---
gemini_api_key = "AIzaSyAkNugx2y8cwtbyf_NKjzR6bdZ7ZFdF6l4"
if not gemini_api_key: 
    raise ValueError("Не задан GEMINI_API_KEY")

logger.info("Настройка Gemini API...")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.0-flash')
logger.info("Gemini API настроен успешно")

# --- Azure Speech ---
speech_key = os.getenv("SPEECH_KEY")
speech_region = os.getenv("SPEECH_REGION")

if not (speech_key and speech_region):
    logger.warning("Azure Speech отключён. Речь будет недоступна.")

# --- Системная инструкция ---
SYSTEM_INSTRUCTION = """
Ты AI-Дос, интеллектуальный помощник для детей 8–12 лет.
Отвечай коротко (до 100 слов), тепло и позитивно.
Поддерживай ребёнка и задавай вопросы.
Используй эмодзи ✨🚀🎨🌟
Всегда представляйся как AI-Дос.
"""

def cleanup_text_for_speech(text):
    if not text:
        return ""
    pattern = re.compile(r'[^a-zA-Zа-яА-Я0-9,.?!\s]')
    return re.sub(pattern, '', text).strip()

def validate_history(history):
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

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "name": "AI-Дос",
        "version": "1.0.0",
        "description": "Интеллектуальный помощник для детей",
        "endpoints": {
            "health": "/api/health",
            "chat": "/api/chat",
            "speech": "/api/speech"
        },
        "status": "online"
    })

# --- CHAT API С УЛУЧШЕННЫМ ЛОГИРОВАНИЕМ ---
@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.json
        logger.debug(f"Получен запрос к /api/chat: {json.dumps(data, ensure_ascii=False)[:200]}...")
        
        if not data:
            return jsonify({"error": "Тело запроса не может быть пустым"}), 400
            
        history = data.get("history", [])
        logger.info(f"Получена история из {len(history)} сообщений")

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
        logger.debug(f"Добавлена системная инструкция")

        # Добавляем историю чата
        for i, msg in enumerate(history):
            role = "model" if msg["role"] == "model" else "user"
            parts = msg.get("parts", [msg.get("content", "")])
            messages.append({
                "role": role,
                "parts": parts
            })
            logger.debug(f"Сообщение {i+1}: роль={role}, частей={len(parts)}")

        logger.info(f"Всего сообщений для Gemini: {len(messages)}")

        def generate():
            """Генератор для потоковой передачи ответа"""
            try:
                logger.info("🚀 Отправка запроса к Gemini API...")
                
                # Логируем первые 500 символов запроса для отладки
                messages_preview = json.dumps(messages, ensure_ascii=False)[:500]
                logger.debug(f"Запрос к Gemini (первые 500 символов): {messages_preview}")
                
                response = model.generate_content_stream(
                    contents=messages
                )

                chunk_count = 0
                for chunk in response:
                    if chunk.text:
                        chunk_count += 1
                        logger.debug(f"Получен чанк {chunk_count}: {len(chunk.text)} символов")
                        yield chunk.text
                
                logger.info(f"✅ Gemini ответил успешно. Всего чанков: {chunk_count}")
                
            except Exception as e:
                logger.error(f"❌ ОШИБКА GEMINI: {str(e)}", exc_info=True)
                # Пытаемся получить больше информации об ошибке
                if hasattr(e, 'response'):
                    logger.error(f"Статус ответа: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
                    logger.error(f"Тело ответа: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
                yield f"Извините, произошла ошибка при генерации ответа. Детали: {str(e)}"

        return Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')

    except Exception as e:
        logger.error(f"Критическая ошибка /api/chat: {e}", exc_info=True)
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

# --- SPEECH API ---
@app.route('/api/speech', methods=['POST', 'OPTIONS'])
def speech():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.json
        if not data:
            return jsonify({"error": "Тело запроса не может быть пустым"}), 400
            
        text = data.get("text")
        logger.debug(f"Запрос на синтез речи: {text[:50]}...")

        if not text:
            return jsonify({"error": "text обязателен"}), 400

        text_clean = cleanup_text_for_speech(text)

        if not speech_key or not speech_region:
            logger.warning("Azure Speech не настроен, возвращаем заглушку")
            return jsonify({
                "audio_base64": None,
                "success": False,
                "message": "Речь временно недоступна"
            }), 200

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
            "User-Agent": "AI-Dos"
        }

        response = requests.post(
            endpoint, 
            data=ssml.encode('utf-8'), 
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        logger.info(f"Речь успешно синтезирована: {len(audio_base64)} символов base64")

        return jsonify({
            "audio_base64": audio_base64,
            "success": True
        })

    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к Azure Speech")
        return jsonify({
            "audio_base64": None,
            "success": False,
            "message": "Таймаут сервиса речи"
        }), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к Azure Speech: {e}")
        return jsonify({
            "audio_base64": None,
            "success": False,
            "message": "Ошибка сервиса речи"
        }), 200
    except Exception as e:
        logger.error(f"Ошибка /api/speech: {e}", exc_info=True)
        return jsonify({
            "audio_base64": None,
            "success": False,
            "message": "Речь временно недоступна"
        }), 200

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return '', 200

    return jsonify({
        "status": "healthy",
        "gemini_configured": bool(gemini_api_key),
        "azure_speech_configured": bool(speech_key and speech_region),
        "redis_configured": redis_client is not None
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    logger.info(f"Запуск сервера на порту {port}, debug={debug}")
    app.run(host='0.0.0.0', port=port, debug=debug)
