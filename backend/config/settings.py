import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env(path):
    """Load a development .env file without overriding real environment variables."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_local_env(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

if not DEBUG and SECRET_KEY == "unsafe-development-key-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY must be configured when DJANGO_DEBUG=false")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "accounts",
    "appointments",
    "communication",
    "payments",
    "prescriptions",
    "services",
    "reviews",
    "dashboard",
    "governance",
    "clinical",
    "registry",
    "interoperability",
    "workforce",
    "operations",
    "channels",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
DB_NAME = os.getenv("DB_NAME", str(BASE_DIR / "db.sqlite3"))
if DB_ENGINE == "django.db.backends.sqlite3" and not Path(DB_NAME).is_absolute():
    DB_NAME = str(BASE_DIR / DB_NAME)

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": DB_NAME,
    }
}
if DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
    DATABASES["default"].update(
        {
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "prefer")},
        }
    )

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Africa/Kampala")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", 12 * 1024 * 1024))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_ANON_RATE", "100/hour"),
        "user": os.getenv("DRF_USER_RATE", "2000/hour"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)


EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "MyDoctor <no-reply@mydoctor.local>")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 15

MOCK_PAYMENTS = env_bool("MOCK_PAYMENTS", DEBUG)
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.10"))
JITSI_BASE_URL = os.getenv("JITSI_BASE_URL", "https://meet.jit.si")
JITSI_APP_ID = os.getenv("JITSI_APP_ID", "")
JITSI_JWT_SECRET = os.getenv("JITSI_JWT_SECRET", "")

# Production security defaults. They remain disabled in local development.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# Operational integrations are configured by the server, never by request URLs.
OFFLINE_ENCRYPTION_KEY = os.getenv("OFFLINE_ENCRYPTION_KEY", "")
PRIVATE_DOCUMENT_MAX_BYTES = int(os.getenv("PRIVATE_DOCUMENT_MAX_BYTES", "10485760"))
CLAMAV_HOST = os.getenv("CLAMAV_HOST", "")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
DICOMWEB_URL = os.getenv("DICOMWEB_URL", "")
DICOMWEB_TOKEN = os.getenv("DICOMWEB_TOKEN", "")
TERMINOLOGY_SERVER_URL = os.getenv("TERMINOLOGY_SERVER_URL", "")
TERMINOLOGY_SERVER_TOKEN = os.getenv("TERMINOLOGY_SERVER_TOKEN", "")
HIE_SERVER_URL = os.getenv("HIE_SERVER_URL", "")
HIE_SERVER_TOKEN = os.getenv("HIE_SERVER_TOKEN", "")
OUTBOX_WEBHOOK_URL = os.getenv("OUTBOX_WEBHOOK_URL", "")
OUTBOX_WEBHOOK_SECRET = os.getenv("OUTBOX_WEBHOOK_SECRET", "")
SMS_WEBHOOK_URL = os.getenv("SMS_WEBHOOK_URL", "")
SMS_WEBHOOK_TOKEN = os.getenv("SMS_WEBHOOK_TOKEN", "")
PUSH_WEBHOOK_URL = os.getenv("PUSH_WEBHOOK_URL", "")
PUSH_WEBHOOK_TOKEN = os.getenv("PUSH_WEBHOOK_TOKEN", "")
NOTIFICATION_CALLBACK_SECRET = os.getenv("NOTIFICATION_CALLBACK_SECRET", "")
COPILOT_ALLOWED_ADAPTERS = env_list("COPILOT_ALLOWED_ADAPTERS")
COPILOT_PROVIDER_URL = os.getenv("COPILOT_PROVIDER_URL", "")
COPILOT_PROVIDER_TOKEN = os.getenv("COPILOT_PROVIDER_TOKEN", "")
RESEARCH_MIN_COHORT = max(5, int(os.getenv("RESEARCH_MIN_COHORT", "10")))
PRIVATE_MEDIA_ROOT = Path(os.getenv("PRIVATE_MEDIA_ROOT") or str(BASE_DIR / "private-media"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "private": {"BACKEND": "operations.storage.PrivateLocalStorage"},
}
if os.getenv("PRIVATE_S3_BUCKET"):
    STORAGES["private"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["PRIVATE_S3_BUCKET"],
            "region_name": os.getenv("PRIVATE_S3_REGION", "eu-west-1"),
            "default_acl": None, "querystring_auth": True, "querystring_expire": 60,
            "file_overwrite": False, "custom_domain": None,
            "object_parameters": {"ServerSideEncryption": "AES256", "CacheControl": "private, no-store"},
        },
    }

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CHANNEL_LAYERS = {"default": {
    "BACKEND": "channels.layers.InMemoryChannelLayer" if DEBUG else "channels_redis.core.RedisChannelLayer",
    **({} if DEBUG else {"CONFIG": {"hosts": [REDIS_URL], "capacity": 100, "expiry": 60}}),
}}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_TIME_LIMIT = 300
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
LAB_CRITICAL_ESCALATION_MINUTES = max(0, int(os.getenv("LAB_CRITICAL_ESCALATION_MINUTES", "0")))
CELERY_BEAT_SCHEDULE = {
    "escalate-critical-lab-results": {"task": "operations.tasks.escalate_critical_lab_results", "schedule": 60.0},
    "deliver-outbox": {"task": "operations.tasks.deliver_events", "schedule": 30.0},
    "deliver-notifications": {"task": "operations.tasks.deliver_notifications", "schedule": 30.0},
    "appointment-reminders": {"task": "operations.tasks.appointment_reminders", "schedule": 3600.0},
    "credential-expiry": {"task": "operations.tasks.credential_expiry", "schedule": 86400.0},
    "refresh-expired-stock": {"task": "operations.tasks.refresh_inventory", "schedule": 3600.0},
}
