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
    "django_filters",
    "drf_spectacular",
    "storages",
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
    "enterprise.apps.EnterpriseConfig",
    "journeys.apps.JourneysConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
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
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
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

MOCK_PAYMENTS = env_bool("MOCK_PAYMENTS", DEBUG)
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.10"))
JITSI_BASE_URL = os.getenv("JITSI_BASE_URL", "https://meet.jit.si")

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

# Account security and public frontend URLs.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
LOGIN_FAILURE_LOCK_THRESHOLD = int(os.getenv("LOGIN_FAILURE_LOCK_THRESHOLD", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
EMAIL_VERIFICATION_MINUTES = int(os.getenv("EMAIL_VERIFICATION_MINUTES", "1440"))
PASSWORD_RESET_MINUTES = int(os.getenv("PASSWORD_RESET_MINUTES", "30"))
MFA_CODE_MINUTES = int(os.getenv("MFA_CODE_MINUTES", "10"))
PHONE_VERIFICATION_MINUTES = int(os.getenv("PHONE_VERIFICATION_MINUTES", "10"))

NOTIFICATION_CALLBACK_SECRET = os.getenv("NOTIFICATION_CALLBACK_SECRET", "")
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
CLAMAV_ENABLED = env_bool("CLAMAV_ENABLED", False)
CLAMAV_REQUIRED = env_bool("CLAMAV_REQUIRED", not DEBUG and CLAMAV_ENABLED)
CLAMAV_HOST = os.getenv("CLAMAV_HOST", "clamav" if CLAMAV_ENABLED else "localhost")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
CLAMAV_TIMEOUT_SECONDS = float(os.getenv("CLAMAV_TIMEOUT_SECONDS", "12"))
DOCUMENT_OCR_ENDPOINT = os.getenv("DOCUMENT_OCR_ENDPOINT", "")
TELEMEDICINE_PROVIDER = os.getenv("TELEMEDICINE_PROVIDER", "jitsi")

# Redis-backed cache is used for readiness checks, rate-limited workflows and
# short-lived coordination. Local development falls back to process memory.
CACHE_URL = os.getenv("CACHE_URL", "")
if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
            "TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300")),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "mydoctor-local-cache",
        }
    }


# OpenAPI documentation. Disable the public schema UI at the edge if not needed.
SPECTACULAR_SETTINGS = {
    "TITLE": "MyDoctor Healthcare Platform API",
    "DESCRIPTION": "Role-scoped APIs for patient care, provider verification, hospital operations, diagnostics, pharmacy, billing and administration.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Private object storage. Local media is retained for development only.
USE_S3 = env_bool("USE_S3", False)
if USE_S3:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "") or None
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "") or None
    AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "virtual")
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = int(os.getenv("AWS_QUERYSTRING_EXPIRE", "300"))
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "private, max-age=300",
        "ServerSideEncryption": os.getenv("AWS_S3_SERVER_SIDE_ENCRYPTION", "AES256"),
    }
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

# Background jobs and reliable notification/outbox processing.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "300"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "240"))
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_BEAT_SCHEDULE = {
    "dispatch-notifications-every-minute": {
        "task": "communication.tasks.dispatch_notification_deliveries",
        "schedule": 60.0,
    },
    "publish-outbox-every-minute": {
        "task": "interoperability.tasks.publish_pending_outbox",
        "schedule": 60.0,
    },
    "appointment-reminders-every-15-minutes": {
        "task": "appointments.tasks.send_scheduled_appointment_reminders",
        "schedule": 900.0,
    },
    "credential-expiry-daily": {
        "task": "registry.tasks.notify_credential_expiry",
        "schedule": 86400.0,
    },
    "subscription-and-stock-scan-hourly": {
        "task": "operations.tasks.expire_subscriptions_and_scan_stock",
        "schedule": 3600.0,
    },
    "enterprise-event-delivery-every-30-seconds": {
        "task": "enterprise.tasks.deliver_pending_enterprise_events",
        "schedule": 30.0,
    },
    "enterprise-provider-health-every-10-minutes": {
        "task": "enterprise.tasks.check_enterprise_provider_health",
        "schedule": 600.0,
    },
    "enterprise-mpi-duplicate-scan-nightly": {
        "task": "enterprise.tasks.scan_master_patient_index",
        "schedule": 86400.0,
    },
    "enterprise-scheduled-reports-every-5-minutes": {
        "task": "enterprise.tasks.dispatch_due_report_schedules",
        "schedule": 300.0,
    },
    "enterprise-security-maintenance-daily": {
        "task": "enterprise.tasks.create_daily_security_operations",
        "schedule": 86400.0,
    },
}


# Real-time WebSocket transport. In-memory transport is safe only for a single
# development/test process; production uses Redis for cross-process fan-out.
USE_INMEMORY_CHANNEL_LAYER = env_bool("USE_INMEMORY_CHANNEL_LAYER", DEBUG)
if USE_INMEMORY_CHANNEL_LAYER:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_REDIS_URL = os.getenv("CHANNEL_REDIS_URL", "") or CELERY_BROKER_URL
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [CHANNEL_REDIS_URL]},
        }
    }

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} request_id={request_id} {message}",
            "style": "{",
        },
        "simple": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "filters": {
        "request_id": {"()": "config.logging.RequestIdFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "mydoctor": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
