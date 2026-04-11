#qubitgyan-backend\qubitgyan\settings.py

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
load_dotenv() # This reads your local .env file!


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-locally-12345')

# SECURITY WARNING: don't run with debug turned on in production!
# We check if we are on Render by looking for the RENDER environment variable
REPLIT = os.environ.get('REPL_ID') is not None
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# Set DEBUG to True locally by default, but allow production to turn it off
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
 
if DEBUG or REPLIT:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

SECRET_KEY = os.environ.get('SECRET_KEY')
if not DEBUG and not SECRET_KEY:
    raise ValueError("The SECRET_KEY environment variable must be set in production!")
elif not SECRET_KEY:
    SECRET_KEY = 'django-insecure-change-me-locally-12345'
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third Party
    'rest_framework',
    'corsheaders',
    
    # Local Apps
    'library',
    'library.api.v2.lexicon',
    'library.api.v2.community',
    'library.api.v2.analytics',
    'library.api.v2.notifications',
    'library.api.v2.assessments',
    'library.api.v2.planner',
    'library.api.v2.spaced_repetition',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Render Static Files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware', # CORS for Next.js
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'library.middleware.request_logging.RequestLoggingMiddleware',
    'library.middleware.error_logging.ErrorLoggingMiddleware',
]

ROOT_URLCONF = 'qubitgyan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'qubitgyan.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        # Look for DATABASE_URL in env, otherwise use local sqlite
        default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
        conn_max_age=600
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- QubitGyan Custom Config ---

# CORS Settings (Allow Next.js to talk to us)
CSRF_TRUSTED_ORIGINS = [
    "https://qubitgyan.vercel.app",
    "https://qubitgyan-admin.vercel.app",
    "https://lexicon-qubitgyan.vercel.app", 
    "http://localhost:3000",                
    "http://localhost:3001",               
    "http://localhost:5173",                
    "https://lexicon-drab.vercel.app", # <-- ADDED THIS URL
]

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://qubitgyan.vercel.app",
    "https://qubitgyan-admin.vercel.app",
    "https://lexicon-qubitgyan.vercel.app",
    "http://localhost:3000", 
    "http://localhost:3001",
    "http://localhost:5173",
    "https://lexicon-drab.vercel.app",
]
FRONTEND_URL = "https://qubitgyan.vercel.app"

# REST Framework Config
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '2000/day', 
        'admissions': '50/day'
    },
}


from datetime import timedelta
from celery.schedules import crontab
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1), # User stays logged in for 1 day
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# --- EMAIL CONFIGURATION (GMAIL) ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('SMTP_USER')
EMAIL_HOST_PASSWORD = os.environ.get('SMTP_PASSWORD')

DEFAULT_FROM_EMAIL = f"QubitGyan Admission <{EMAIL_HOST_USER}>"

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SR_KEY = os.environ.get('SUPABASE_SR_KEY')


# Merriam-Webster API Key for Lexicon Fallback
MERRIAM_WEBSTER_API_KEY = os.environ.get('MERRIAM_WEBSTER_API_KEY', '')
MW_DICTIONARY_KEY = os.environ.get('MW_DICTIONARY_KEY', '')
MW_THESAURUS_KEY = os.environ.get('MW_THESAURUS_KEY', '')


# ----------------------------------------
# REDIS CACHE CONFIGURATION
# ----------------------------------------

REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "qubitgyan",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "qubitgyan-cache",
        }
    }

# ---------------------------------------------------
# LOGGING CONFIGURATION
# ---------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "[{asctime}] {levelname} "
                "{name} {message}"
            ),
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },

    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# Celery Configuration

CELERY_BROKER_URL = REDIS_URL or os.environ.get("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND") or (REDIS_URL or "cache+memory://")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = DEBUG and not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = True
ENABLE_ASYNC_TASKS = _env_bool("ENABLE_ASYNC_TASKS", default=bool(CELERY_BROKER_URL))


LEXICON_NIGHTLY_PIPELINE_HOUR = int(os.environ.get("LEXICON_NIGHTLY_PIPELINE_HOUR", "0"))
LEXICON_NIGHTLY_PIPELINE_MINUTE = int(os.environ.get("LEXICON_NIGHTLY_PIPELINE_MINUTE", "0"))

CELERY_BEAT_SCHEDULE = {
    "lexicon-midnight-pipeline": {
        "task": "library.api.v2.lexicon.tasks.run_midnight_lexicon_pipeline",
        "schedule": crontab(minute=LEXICON_NIGHTLY_PIPELINE_MINUTE, hour=LEXICON_NIGHTLY_PIPELINE_HOUR),
    },
}
