# AI PlagaScan — Internet Plagiarism Edition

This version removes the local sample-document plagiarism corpus. Uploaded files and pasted text are submitted to the Copyleaks Authenticity API with Internet scanning enabled. The application receives Copyleaks webhooks and updates the report automatically.

## 1. Requirements
- Python 3.10+
- VS Code
- Internet connection
- A Copyleaks account and API key
- ngrok (or another HTTPS tunnel) for local webhook testing
- Tesseract OCR for PNG/JPG/JPEG uploads

## 2. Install
Open the project folder in VS Code terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

For image uploads on Windows, install Tesseract OCR once:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

Restart the terminal after installation so `tesseract.exe` is available on `PATH`.

## 3. Configure Copyleaks
Copy `.env.example` to `.env` and fill in:

```env
COPYLEAKS_EMAIL=your-copyleaks-email
COPYLEAKS_API_KEY=your-api-key
COPYLEAKS_SANDBOX=false
COPYLEAKS_WEBHOOK_BASE_URL=https://YOUR-NGROK-DOMAIN
COPYLEAKS_WEBHOOK_SECRET=use-a-long-random-secret
```

For real Internet results, keep `COPYLEAKS_SANDBOX=false`. Sandbox mode is for integration testing and returns mock results.

## 4. Start Flask
```powershell
python backend/app.py
```
The site normally runs at `http://127.0.0.1:5000`.

## 5. Expose the webhook locally
Copyleaks cannot call `127.0.0.1` on your computer. Install ngrok, then in a second terminal run:

```powershell
ngrok http 5000
```

Copy the HTTPS forwarding URL, for example `https://abc123.ngrok-free.app`, into `.env` as `COPYLEAKS_WEBHOOK_BASE_URL`. Restart Flask after changing `.env`.

## 6. Test
1. Log in.
2. Open **Upload Document** or **Text Checker**.
3. Submit a document/text with at least 20 characters.
4. The report first shows `processing`.
5. Copyleaks scans Internet sources.
6. Copyleaks calls the webhook.
7. The report refreshes and shows the online similarity score and source URLs.

## 7. Important
- `backend/seed.py` is no longer used and has been removed.
- Upload and text-check routes no longer compare against local seed documents.
- SQLite is still used by default for users/reports.
- Do not commit `.env` or your API key.
- Production Copyleaks scans may consume credits.

The database initializer still creates application roles and a default authority account on first run. That is separate from the old sample plagiarism corpus. Change the default admin password before production use.
