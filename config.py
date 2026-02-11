"""
Configuration module for Jobs.AI application.
Centralizes all environment variables, constants, and configuration settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===========================
# Directory Paths
# ===========================
RESUME_FOLDER = os.getenv("RESUME_FOLDER", "data/resumes")
EMBEDDING_CACHE = os.getenv("EMBEDDING_CACHE", "data/resume_embeddings.pkl")
CONTACT_CACHE = os.getenv("CONTACT_CACHE", "data/contact_info_cache.pkl")
ATS_CACHE = os.getenv("ATS_CACHE", "data/ats_scores_cache.pkl")

# Ensure resume folder exists
Path(RESUME_FOLDER).mkdir(parents=True, exist_ok=True)

# ===========================
# SMTP Email Configuration
# ===========================
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# ===========================
# Ollama Configuration
# ===========================
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# ===========================
# Batch Processing Configuration
# ===========================
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "6"))  # Increased for faster processing
EMAIL_DELAY_SECONDS = float(os.getenv("EMAIL_DELAY_SECONDS", "2"))
MAX_EMAIL_RETRIES = int(os.getenv("MAX_EMAIL_RETRIES", "3"))

# ===========================
# Regex Patterns
# ===========================
EMAIL_PATTERNS = [
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    r'\b[A-Za-z0-9]+[\._]?[A-Za-z0-9]+[@]\w+[.]\w{2,3}\b',
    r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    r'Email\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
    r'E-mail\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
]

PHONE_PATTERNS = [
    r'[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}',
    r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
    r'\b\d{10}\b',
    r'(?:Phone|Mobile|Tel|Contact)[\s:]*([+\d\s\-\(\)]+)',
]

# ===========================
# UI Configuration
# ===========================
APP_TITLE = "Advanced ATS Resume Shortlister Pro"
APP_ICON = "🎯"
PAGE_LAYOUT = "wide"

# Score thresholds
SCORE_EXCELLENT = 85
SCORE_GOOD = 70
SCORE_AVERAGE = 60

# ===========================
# Common Tech Keywords
# ===========================
TECH_KEYWORDS = [
    'python', 'java', 'javascript', 'sql', 'aws', 'azure', 'docker',
    'kubernetes', 'react', 'node', 'machine learning', 'ai', 'data',
    'cloud', 'devops', 'agile', 'api', 'database', 'frontend', 'backend'
]

# ===========================
# Validation
# ===========================
def validate_smtp_config():
    """Check if SMTP configuration is valid."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False, "SMTP_EMAIL and SMTP_PASSWORD must be set in .env file"
    return True, "SMTP configuration valid"

def validate_ollama_config():
    """Check if Ollama configuration is valid."""
    if not OLLAMA_API_URL or not OLLAMA_MODEL:
        return False, "OLLAMA_API_URL and OLLAMA_MODEL must be set"
    return True, "Ollama configuration valid"
