import os, logging
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

logging.getLogger(__name__).warning(
    "EMAIL_BACKEND=%s; EMAIL_HOST_USER=%s",
    os.getenv("EMAIL_BACKEND"), os.getenv("EMAIL_HOST_USER")
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")   # <— вместо просто load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "api",
    # 3rd‑party
    "rest_framework",
    "django_filters",
    "corsheaders",
    "rest_framework_simplejwt",
    "drf_yasg",
    "drf_spectacular",
    "drf_spectacular_sidecar",             # <— добавь
    # local
]

AUTH_USER_MODEL = "api.User"   # или "accounts.User", если приложение называется иначе

DB_DIR = BASE_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)  # авто-создание папки

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "snapAI.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "snapAI.wsgi.application"

# ——— База (SQLite) ———

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_DIR / "db.sqlite3",
    }
}

# ——— Стастика/медиа ———
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", BASE_DIR / "media")

# ——— DRF ———

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SnapAI API",
    "DESCRIPTION": "Документация API",
    "VERSION": "1.0.0",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
}

# ——— CORS ———
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if os.getenv("CORS_ALLOWED_ORIGINS") else []
CORS_ALLOW_ALL_ORIGINS = not CORS_ALLOWED_ORIGINS

CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if os.getenv("CSRF_TRUSTED_ORIGINS") else []

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEBUG = os.getenv("DEBUG", "True") == "True"

# --- Email ---
if os.getenv("EMAIL_BACKEND", "").lower() == "smtp":
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
else:
    # Dev: письма не отправляются, а печатаются в консоль/логи
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "dev@localhost")


# --- SUPERUSER ---
SUPERUSER_EMAIL = os.getenv('SUPERUSER_EMAIL', 'admin@example.com')
SUPERUSER_PASSWORD = os.getenv('SUPERUSER_PASSWORD', 'Admin_333')

