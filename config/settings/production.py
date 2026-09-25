"""Production settings. Every secret must be provided through the environment."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")  # noqa: F405

database_url = env("DATABASE_URL", default=None)  # noqa: F405
if not database_url:
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")

DATABASES = {"default": env.db_url("DATABASE_URL")}  # noqa: F405

# 운영에서 가상 시간이 실수로 켜진 채 배포되지 않도록 명시적 확인값을 요구한다.
if FESTIVAL_TIME_ENABLED and not env.bool(  # noqa: F405
    "FESTIVAL_TIME_PRODUCTION_ACK", default=False
):
    raise ImproperlyConfigured(
        "FESTIVAL_TIME_ENABLED=True in production requires FESTIVAL_TIME_PRODUCTION_ACK=True."
    )

# 운영 업로드 파일은 Cloudflare R2의 S3 호환 API에 저장한다.
# R2를 명시적으로 끄지 않는 한 필수 환경변수가 없으면 시작 단계에서 실패한다.
R2_ENABLED = env.bool("R2_ENABLED", default=True)  # noqa: F405
if R2_ENABLED:
    r2_account_id = env("R2_ACCOUNT_ID")  # noqa: F405
    r2_bucket_name = env("R2_BUCKET_NAME")  # noqa: F405
    r2_access_key_id = env("R2_ACCESS_KEY_ID")  # noqa: F405
    r2_secret_access_key = env("R2_SECRET_ACCESS_KEY")  # noqa: F405
    r2_public_domain = env("R2_PUBLIC_DOMAIN")  # noqa: F405

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": r2_access_key_id,
                "secret_key": r2_secret_access_key,
                "bucket_name": r2_bucket_name,
                "endpoint_url": f"https://{r2_account_id}.r2.cloudflarestorage.com",
                "region_name": "auto",
                "custom_domain": r2_public_domain,
                "url_protocol": "https:",
                "querystring_auth": False,
                "default_acl": None,
                "file_overwrite": False,
                "location": "media",
                "object_parameters": {
                    "CacheControl": "public, max-age=31536000, immutable"
                },
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
