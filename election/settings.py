"""
election/settings.py  —  Production-ready configuration.

Sensitive values are read from .env via python-dotenv.
Never hardcode secrets here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# —— Core ———————————————————————————————————————————————————————————————————
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DEBUG", "False") == "True"

# Reads comma-separated hosts from env, e.g. "myapp.railway.app,myapp.up.railway.app"
_raw_hosts = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]
ALLOWED_HOSTS.append("healthcheck.railway.app")  # required for Railway healthchecks
# Required for Railway's HTTPS proxy — include your public domain(s) here
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS
    if h not in ("127.0.0.1", "localhost")
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# —— Apps ———————————————————————————————————————————————————————————————————
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.staticfiles",   # needed for whitenoise collectstatic
    "social_django",
    "voting",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # serve static files, right after Security
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
]

ROOT_URLCONF = "election.urls"
WSGI_APPLICATION = "election.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
            ],
        },
    }
]

# —— Static files ————————————————————————————————————————————————————————————
STATIC_URL = "/static/"
STATIC_ROOT = Path("/staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# —— Database ————————————————————————————————————————————————————————————————
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "election_db"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# Railway provides a single DATABASE_URL — parse it if present
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    import urllib.parse
    _u = urllib.parse.urlparse(_db_url)
    DATABASES["default"].update({
        "NAME":     _u.path.lstrip("/"),
        "USER":     _u.username,
        "PASSWORD": _u.password,
        "HOST":     _u.hostname,
        "PORT":     str(_u.port or 5432),
    })

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 3600

AUTHENTICATION_BACKENDS = [
    "social_core.backends.google.GoogleOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY    = os.environ["GOOGLE_OAUTH2_CLIENT_ID"]
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ["GOOGLE_OAUTH2_CLIENT_SECRET"]

SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "ashoka.edu.in")
SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS = [ALLOWED_EMAIL_DOMAIN]

SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
    "voting.pipeline.provision_voter",
)

SOCIAL_AUTH_LOGIN_REDIRECT_URL    = "/"
SOCIAL_AUTH_LOGIN_ERROR_URL       = "/auth/error/"
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = "/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "loggers": {
        "voting": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "social": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"