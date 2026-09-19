"""Settings shared by every environment."""

from datetime import date
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

KAKAO_CLIENT_ID = env("KAKAO_REST_API_KEY", default="")
KAKAO_REDIRECT_URI = env("KAKAO_REDIRECT_URI")
KAKAO_CLIENT_SECRET = env("KAKAO_CLIENT_SECRET", default="")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-scaffold-only-secret-key")
DEBUG = env.bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts.apps.AccountsConfig",
    "apps.admins.apps.AdminsConfig",
    "apps.booths.apps.BoothsConfig",
    "apps.lanterns.apps.LanternsConfig",
    "apps.coupons.apps.CouponsConfig",
    "apps.notices.apps.NoticesConfig",
    "apps.lost_items.apps.LostItemsConfig",
    "apps.performances.apps.PerformancesConfig",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Custom authentication is intentionally pending the Kakao/admin auth decision.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "2026 Fall Festival API",
    "DESCRIPTION": "Dongguk University 2026 fall festival backend API",
    "VERSION": "1.0.0",
}

ADMIN_API_TOKEN = env("ADMIN_API_TOKEN", default="")

FESTIVAL_START_DATE = date(2026, 9, 29)
FESTIVAL_END_DATE = date(2026, 10, 1)

# 분실물 이미지 업로드 설정
LOST_ITEM_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
LOST_ITEM_IMAGE_MAX_BYTES = 5 * 1024 * 1024
