import os


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./liveslide.db")
API_JWT_SECRET = os.getenv("API_JWT_SECRET", "local-development-secret-change-me")
API_JWT_EXPIRES_SECONDS = int(os.getenv("API_JWT_EXPIRES_SECONDS", "3600"))
API_SERVICE_KEY = os.getenv("API_SERVICE_KEY", "change-me-service-key")
PHOTO_STORAGE_DIR = os.getenv("PHOTO_STORAGE_DIR", "./data/photos")
AGENTS_URL = os.getenv("AGENTS_URL", "")
DISPATCH_MODE = os.getenv("DISPATCH_MODE", "mock")
MAX_BBOX_AREA_DEG2 = float(os.getenv("MAX_BBOX_AREA_DEG2", "4"))
