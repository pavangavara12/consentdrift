import os

# Disable SQLAlchemy C extensions to ensure pure-Python execution under strict Windows Application Control
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./consentdrift.db")

raw_jwt_secret = os.getenv("JWT_SECRET", "").strip()
if not raw_jwt_secret:
    if ENVIRONMENT not in ("dev", "development", "test", "testing"):
        raise RuntimeError("JWT_SECRET environment variable is missing outside development mode.")
    JWT_SECRET = "consentdrift-dev-secret-key-32-chars-long-do-not-use-in-prod"
else:
    JWT_SECRET = raw_jwt_secret

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
