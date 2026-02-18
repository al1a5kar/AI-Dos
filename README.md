# 祐祐 - AI 知識夥伴 🚀

![祐祐 AI 夥伴](./public/yoyo-avatar.png)

這是一個專為兒童設計的 AI 知識夥伴，名叫「祐祐」。它不僅能用充滿情感的聲音回答孩子們的各種問題，還能「看見」孩子們分享的圖片（例如他們的畫作），並給予溫暖的鼓勵和讚美。

## ✨ 主要功能

*   **情感語音合成**：祐祐的回答會被拆分成多個帶有不同情感（如開朗、安慰、興奮）的語音片段，並一次性合成為自然、有溫度的語音。
*   **多模態理解**：孩子可以拍照或上傳圖片，祐祐能夠理解圖片內容並作出相關的回應，特別適合讚美孩子的畫作。
*   **前後端分離架構**：前端為純靜態網站，後端為獨立的 Web Service，是現代化、可擴展的網頁應用架構。
*   **兒童友善的互動**：經過特殊設計的系統提示 (System Prompt) 讓祐祐的回應總是充滿想像力、鼓勵性和正能量。
*   **語音輸入**：支援麥克風語音輸入，方便不擅長打字的孩子使用。

## 🛠️ 使用技術

*   **後端 (Backend)**:
    *   **框架**: Flask
    *   **語言模型**: Google Gemini 1.5 Flash (多模態 & JSON 輸出)
    *   **語音合成 (TTS)**: Azure Cognitive Services Speech
    *   **伺服器**: Gunicorn
    *   **部署**: **Render (Web Service)**

*   **前端 (Frontend)**:
    *   HTML5 / CSS3 / JavaScript
    *   Web Speech API (語音辨識)
    *   Fetch API
    *   **部署**: **Render (Static Site)**

## 🚀 如何在本地運行

為了模擬正式的部署環境，我們將在本地分別啟動後端和前端伺服器。

1.  **複製專案**
    ```bash
    git clone https://github.com/ganbing0630/yoyo-ai-partner.git
    cd yoyo-ai-partner
    ```

2.  **建立虛擬環境並安裝依賴**
    ```bash
    # 建立虛擬環境
    python -m venv venv
    # 啟用虛擬環境 (macOS/Linux)
    source venv/bin/activate
    # 啟用虛擬環境 (Windows)
    # .\venv\Scripts\activate
    
    # 安裝所有依賴
    pip install -r requirements.txt
    ```

3.  **設定環境變數**
    *   在專案根目錄建立一個 `.env` 檔案。
    *   填入必要的 API 金鑰：
        ```
        GEMINI_API_KEY="YOUR_GEMINI_KEY"
        SPEECH_KEY="YOUR_AZURE_SPEECH_KEY"
        SPEECH_REGION="YOUR_AZURE_SPEECH_REGION"
        ```

4.  **啟動後端伺服器 (第一個終端機)**
    *   在專案根目錄執行以下指令，啟動 Flask 開發伺服器：
    ```bash
    flask --app api/chat run
    ```
    *   您應該會看到伺服器在 `http://127.0.0.1:5000` 上運行。**請保持這個終端機開啟。**

5.  **啟動前端伺服器 (第二個終端機)**
    *   打開一個**新的終端機視窗**。
    *   進入 `public` 資料夾，並啟動一個簡單的 HTTP 伺服器：
    ```bash
    cd public
    python -m http.server 8080
    ```
    *   您的前端現在運行在 `http://127.0.0.1:8080` 上。

6.  **修改 API 路徑並測試**
    *   為了讓前端能找到在 `5000` 埠運行的後端，請**暫時修改** `public/script.js` 檔案中的 `API_URL`：
        ```javascript
        // const API_URL = "/api/chat"; // 先註解掉這一行
        const API_URL = "http://127.0.0.1:5000/api/chat"; // 暫時使用這一行
        ```
    *   現在，在您的瀏覽器中打開 **`http://127.0.0.1:8080`**，您就可以與「祐祐」進行完整的互動測試了！
    *   **重要提示**: 當您要將修改推送到 GitHub 進行部署時，請記得將 `API_URL` **改回**相對路徑 `"/api/chat"`。


## 部署到 Render

這個專案的架構非常適合在 Render 上進行前後端分離部署。您需要建立兩個服務：

#### 1. 後端：Web Service

*   **平台**: Render
*   **服務類型**: Web Service
*   **環境**: Python
*   **建置指令 (`Build Command`)**: `pip install -r requirements.txt`
*   **啟動指令 (`Start Command`)**: `gunicorn 'api.chat:app'`
*   **環境變數**: 在 Render 的儀表板中設定您的 `GEMINI_API_KEY`, `SPEECH_KEY`, `SPEECH_REGION`。

#### 2. 前端：Static Site

*   **平台**: Render
*   **服務類型**: Static Site
*   **發布目錄 (`Publish Directory`)**: `public`
*   **重寫/轉發規則 (`Redirects/Rewrites`)**:
    *   **Action**: `Rewrite`
    *   **Source**: `/api/:path*`
    *   **Destination**: `https://<您的後端服務網址>.onrender.com/api/:path*`

---
*這個專案是作為 AI 應用開發與現代化部署的範例而創建的。*