# Jobs.AI - Setup & Running Guide

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Edit the `.env` file with your credentials:

```env
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key

# SMTP Email Configuration
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### 3. Start the Application

Run the FastAPI server using `uvicorn`:

```bash
uvicorn api:app --reload
```

The app will generally be available at:
- **Web Interface**: [http://localhost:8000](http://localhost:8000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

## 📋 Project Structure

```
Jobs.Ai-main/
├── api.py                    # Main FastAPI Backend
├── config.py                 # Configuration
├── .env                      # Secrets (API keys, Email)
├── requirements.txt          # Dependencies
├── data/                     # Data storage (resumes, history.json)
├── scripts/                  # Utility scripts
├── web/                      # Frontend (HTML/JS/CSS)
├── utils/                    # Utility modules
└── services/                 # Service modules
```

## 🔧 Troubleshooting

### Import Errors
```bash
pip install -r requirements.txt --upgrade
```

### Testing Gemini Integration
Run the verification script:
```bash
python scripts/verify_gemini.py
```
