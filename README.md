# AI PlagaScan — Internet Plagiarism Edition

> **Live Website / Public Demo**: [https://ai-plagascan-2-0-1.onrender.com](https://ai-plagascan-2-0-1.onrender.com)  
> **Repository**: [https://github.com/Pratik6251x/AI-PlagaScan-2.0](https://github.com/Pratik6251x/AI-PlagaScan-2.0)

AI PlagaScan integrates the Copyleaks Authenticity API with live Internet scanning. Uploaded files (PDF, DOCX, PPTX, Images via OCR) and pasted text are scanned across the web in real-time, receiving Copyleaks webhooks and updating the interactive report automatically.

---

## 🌐 Live Website & Deployment

### Option A: 1-Click Cloud Deployment (Render)
You can deploy this project online for free with [Render](https://render.com):
1. Sign in to [Render](https://render.com) using your GitHub account (`Pratik6251x`).
2. Click **New +** → **Blueprint** (or **Web Service**).
3. Connect the repository **`Pratik6251x/AI-PlagaScan-2.0`**.
4. Render will automatically detect [`render.yaml`](render.yaml) and [`Procfile`](Procfile) and build the application using `gunicorn wsgi:app`.
5. Under Environment Variables, set your `COPYLEAKS_EMAIL`, `COPYLEAKS_API_KEY`, and `SECRET_KEY`.
6. Your live web app URL will be generated (e.g., `https://ai-plagascan.onrender.com`).

### Option B: Live Public Tunnel via ngrok
When running locally with internet access:
```powershell
python backend/app.py
```
And in another terminal:
```powershell
ngrok http 5000
```
Use the public ngrok forwarding URL (e.g., `https://monorail-consult-eardrum.ngrok-free.dev`) for public web access and receiving Copyleaks webhook callbacks.

---

## 1. Requirements
- Python 3.10+
- VS Code
- Internet connection
- A Copyleaks account and API key
- ngrok (or another HTTPS tunnel) for local webhook testing
- Tesseract OCR for PNG/JPG/JPEG uploads

---

## 2. Installation & Setup
Open the project folder in terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks script execution:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

For image uploads with OCR on Windows, install Tesseract OCR once:
```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

---

## 3. Configure Environment
Copy `.env.example` to `.env` and fill in your credentials:

```env
SECRET_KEY=your-random-secret-key
DB_BACKEND=sqlite
COPYLEAKS_EMAIL=your-copyleaks-email
COPYLEAKS_API_KEY=your-api-key
COPYLEAKS_SANDBOX=false
COPYLEAKS_WEBHOOK_BASE_URL=https://YOUR-NGROK-DOMAIN
COPYLEAKS_WEBHOOK_SECRET=use-a-long-random-secret
```

---

## 4. Run the Application

### Development Server:
```powershell
python backend/app.py
```
Runs at `http://127.0.0.1:5000`.

### Production WSGI Server:
```powershell
python wsgi.py
# or using gunicorn:
gunicorn wsgi:app
```

---

## 5. Copyleaks Webhook Setup
Copyleaks sends scan results via webhooks. Start an ngrok tunnel:
```powershell
ngrok http 5000
```
Set the forwarding URL in `.env` as `COPYLEAKS_WEBHOOK_BASE_URL`.

---

## 6. How It Works
1. Log in or create an account.
2. Open **Upload Document** or **Text Checker**.
3. Submit a document or text (at least 20 characters).
4. The report status is set to `processing`.
5. Copyleaks scans indexed internet sources.
6. The webhook callback receives similarity results, matches, and source URLs.
7. The report updates in real time with the plagiarism score and breakdown.

---

## 7. Security Notes
- `.env` contains private API keys and is excluded via `.gitignore`.
- Database files (`database/*.db`) and generated user uploads/reports are excluded from git.
