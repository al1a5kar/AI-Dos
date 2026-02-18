// script.js (полная версия)

document.addEventListener("DOMContentLoaded", () => {
    // --- Определение переменных ---
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const micBtn = document.getElementById("mic-btn");
    const toggleSpeechBtn = document.getElementById("toggle-speech-btn");
    const cameraBtn = document.getElementById("camera-btn");
    const uploadBtn = document.getElementById("upload-btn");
    const fileInput = document.getElementById("file-input");
    const cameraInput = document.getElementById("camera-input");
    const gameBtn = document.getElementById("game-btn");

    // --- Настройка API URL (ИСПРАВЛЕНО!) ---
    const CHAT_API_URL = "https://ai-dos.onrender.com/api/chat";
    const SPEECH_API_URL = "https://ai-dos.onrender.com/api/speech";

    let conversationHistory = [];
    let currentAudio = null;
    let userId = null;
    let isSpeechEnabled = true;

    // --- Функции инициализации ---
    function initializeSpeechSetting() {
        const savedPreference = localStorage.getItem('dos_speech_enabled');
        if (savedPreference !== null) {
            isSpeechEnabled = (savedPreference === 'true');
        }
        updateSpeechButtonUI();
    }

    function updateSpeechButtonUI() {
        toggleSpeechBtn.style.display = 'flex';
        if (isSpeechEnabled) {
            toggleSpeechBtn.textContent = '🔊';
            toggleSpeechBtn.classList.remove('muted');
        } else {
            toggleSpeechBtn.textContent = '🔇';
            toggleSpeechBtn.classList.add('muted');
        }
    }

    function getOrSetUserId() {
        let storedId = localStorage.getItem('dos_user_id');
        if (storedId) {
            userId = storedId;
        } else {
            userId = 'user_' + Date.now().toString(36) + Math.random().toString(36).substr(2);
            localStorage.setItem('dos_user_id', userId);
        }
        console.log("Текущий ID пользователя:", userId);
    }

    // --- Основные функции взаимодействия ---
    function handleSendMessage(message, imageBase64 = null) {
        if (!message && !imageBase64) return;
        addMessageToChatBox(message, "user", imageBase64);
        sendMessageToBackend(message, imageBase64);
    }

    const sendMessageToBackend = async (message, imageBase64 = null) => {
        userInput.disabled = true;

        const messageParts = [];
        if (message) messageParts.push(message);
        if (imageBase64) {
            const match = imageBase64.match(/^data:(image\/\w+);base64,(.*)$/);
            if (match) messageParts.push({ inline_data: { mime_type: match[1], data: match[2] } });
        }
        conversationHistory.push({ role: 'user', parts: messageParts });

        if (currentAudio) currentAudio.pause();

        const aiMessageElement = createMessageElement("ai");
        const p = aiMessageElement.querySelector('p');
        chatBox.appendChild(aiMessageElement);

        p.classList.add('typing-cursor');
        p.innerHTML = '<span class="thinking-dot">.</span><span class="thinking-dot">.</span><span class="thinking-dot">.</span>';
        let isFirstChunk = true;

        try {
            const response = await fetch(CHAT_API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    history: conversationHistory,
                    userId: userId
                }),
            });

            if (!response.ok) throw new Error(`Ошибка сервера ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });

                if (isFirstChunk && chunk) {
                    p.textContent = "";
                    isFirstChunk = false;
                }
                fullText += chunk;
                p.textContent = fullText;
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            if (isFirstChunk) {
                p.textContent = "Хм... кажется, я не знаю, что сказать.";
            }
            p.classList.remove('typing-cursor');

            conversationHistory.push({ role: 'model', parts: [fullText] });
            fetchAndPlayAudio(fullText);

        } catch (error) {
            p.classList.remove('typing-cursor');
            p.textContent = `Ой, AI-Дос потерял связь (${error.message})`;
            console.error("Поймана ошибка:", error);
            if (conversationHistory.length > 0 && conversationHistory[conversationHistory.length - 1].role === 'user') {
                conversationHistory.pop();
            }
        } finally {
            userInput.disabled = false;
            userInput.focus();
        }
    };

    const fetchAndPlayAudio = async (text) => {
        if (!isSpeechEnabled || !text) return;

        try {
            const response = await fetch(SPEECH_API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: text }),
            });
            if (!response.ok) throw new Error(`Ошибка сервера речи: ${response.status}`);
            const data = await response.json();
            if (data.audio_base64) {
                playAudio(data.audio_base64);
            }
        } catch (error) {
            console.error("Не удалось получить речь:", error);
        }
    };

    const playAudio = (base64Audio) => {
        if (!isSpeechEnabled || !base64Audio) return;
        if (currentAudio) currentAudio.pause();

        const audioSource = `data:audio/mpeg;base64,${base64Audio}`;
        currentAudio = new Audio(audioSource);
        currentAudio.onplaying = () => toggleSpeechBtn.classList.add('speaking');
        currentAudio.onpause = () => toggleSpeechBtn.classList.remove('speaking');
        currentAudio.onended = () => {
            toggleSpeechBtn.classList.remove('speaking');
            currentAudio = null;
        };
        currentAudio.play();
    };

    // --- Вспомогательные функции UI ---
    function addMessageToChatBox(message, sender, imageBase64 = null) {
        const messageElement = createMessageElement(sender, message, imageBase64);
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function createMessageElement(sender, messageText = "", imageBase64 = null) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("message", `${sender}-message`);

        if (sender === 'ai') {
            const avatar = document.createElement("img");
            avatar.src = "dos-avatar.png";
            avatar.alt = "ai-avatar";
            avatar.className = "avatar";
            messageElement.appendChild(avatar);
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (messageText || sender === 'ai') {
            const p = document.createElement("p");
            p.textContent = messageText;
            contentDiv.appendChild(p);
        }

        if (imageBase64 && sender === 'user') {
            const img = document.createElement('img');
            img.src = imageBase64;
            img.alt = "uploaded-image";
            img.onclick = () => window.open(imageBase64);
            contentDiv.appendChild(img);
        }
        messageElement.appendChild(contentDiv);
        return messageElement;
    }

    // --- Обработчики событий ---
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (message) {
            userInput.value = "";
            handleSendMessage(message);
        }
    });

    gameBtn.addEventListener('click', () => {
        handleSendMessage("Давай поиграем в загадки!");
    });

    const handleFileSelection = (event) => {
        const file = event.target.files[0];
        if (!file) return;
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const message = userInput.value.trim();
                userInput.value = "";
                handleSendMessage(message, e.target.result);
            };
            reader.readAsDataURL(file);
        } else {
            alert(`Извини, AI-Дос пока понимает только изображения!`);
        }
        event.target.value = '';
    };
    
    cameraBtn.addEventListener('click', () => cameraInput.click());
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelection);
    cameraInput.addEventListener('change', handleFileSelection);

    toggleSpeechBtn.addEventListener('click', () => {
        isSpeechEnabled = !isSpeechEnabled;
        localStorage.setItem('dos_speech_enabled', isSpeechEnabled);
        updateSpeechButtonUI();
        if (!isSpeechEnabled && currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
    });

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = 'ru-RU';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => micBtn.classList.add("recording");
        recognition.onresult = (event) => handleSendMessage(event.results[0][0].transcript);
        recognition.onerror = (event) => console.error("Ошибка распознавания речи:", event.error);
        recognition.onend = () => micBtn.classList.remove("recording");

        micBtn.addEventListener("click", () => recognition.start());
    } else {
        micBtn.style.display = "none";
    }

    // --- Точка входа ---
    getOrSetUserId();
    initializeSpeechSetting();
});
