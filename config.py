import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Application configuration for college prototype."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-12345')
    
    # SQLite Database Path
    DATABASE = os.environ.get('DATABASE', str(BASE_DIR / 'emergency_cloud.db'))
    
    # File Storage Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Max 16MB file size
    ALLOWED_EXTENSIONS = {'pdf', 'txt'}
    
    # AI Summarizer Configuration (Auto-switches to Gemini if API key is provided)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash').strip()
    
    _mock_env = os.environ.get('AI_MOCK_MODE')
    if _mock_env is not None:
        AI_MOCK_MODE = _mock_env.lower() in ('true', '1', 't', 'yes')
    else:
        AI_MOCK_MODE = not bool(GEMINI_API_KEY)
