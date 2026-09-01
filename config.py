import os
from datetime import timedelta
from pathlib import Path

basedir = Path(__file__).resolve().parent

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me-in-production-use-long-random-string-1234567890")
    DATABASE = os.getenv("DATABASE_URL", str(basedir / "instance" / "ligtas.sqlite"))
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # set True in ProductionConfig
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    # Rate limit
    RATELIMIT_STORAGE_URI = "memory://"
    # Demo flag
    IS_DEMO = os.getenv("IS_DEMO", "true").lower() == "true"

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    # Fail loud if still using dev secret
    @staticmethod
    def validate():
        secret = os.getenv("SECRET_KEY", "")
        if not secret or secret.startswith("dev-change-me"):
            raise RuntimeError("SECRET_KEY must be set to a strong random value in production")

class TestingConfig(BaseConfig):
    TESTING = True
    DATABASE = ":memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
