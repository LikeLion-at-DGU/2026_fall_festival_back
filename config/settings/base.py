"""Settings shared by every environment."""

from datetime import date
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    ADMIN_HOSTS=(list, ["admin.localhost"]),
    REDIS_URL=(str, "redis://127.0.0.1:6379/1"),
    R2_ENABLED=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

KAKAO_CLIENT_ID = env("KAKAO_REST_API_KEY", default="")
KAKAO_REDIRECT_URI = env("KAKAO_REDIRECT_URI")
KAKAO_CLIENT_SECRET = env("KAKAO_CLIENT_SECRET", default="")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-scaffold-only-secret-key")
DEBUG = env.bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# 관리자 API를 서브도메인으로 분리하기 위한 호스트 목록 (SubdomainURLRoutingMiddleware).
# ALLOWED_HOSTS에도 반드시 포함되어야 합니다.
ADMIN_HOSTS = env.list("ADMIN_HOSTS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "storages",
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
    "config.middleware.SubdomainURLRoutingMiddleware",
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
R2_ENABLED = env.bool("R2_ENABLED")

# Redis 연결만 준비한다. 실제 캐시 읽기/쓰기와 DRF throttle 적용은 기능별로 추가한다.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

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
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "관리자 토큰 또는 사용자 JWT 토큰",
            }
        }
    },
    "SECURITY": [{"BearerAuth": []}],
}

ADMIN_API_TOKEN = env("ADMIN_API_TOKEN", default="")

FESTIVAL_START_DATE = date(2026, 9, 29)
FESTIVAL_END_DATE = date(2026, 10, 1)

# 분실물 이미지 업로드 설정
LOST_ITEM_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
LOST_ITEM_IMAGE_MAX_BYTES = 5 * 1024 * 1024
