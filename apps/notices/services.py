"""Notices business logic and write operations."""

import os
import uuid
from typing import Any

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.notices.models import Notice
from common.exceptions import FileSizeExceeded, InvalidImageFile

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@transaction.atomic
def create_notice(
    *,
    title: str,
    content: str,
    type: str = Notice.Type.NORMAL,
    image_url: str | None = None,
    admin: Any = None,
) -> Notice:
    """새로운 공지사항을 생성합니다."""
    return Notice.objects.create(
        title=title,
        content=content,
        type=type,
        image_url=image_url,
        admin=admin,
    )


@transaction.atomic
def update_notice(
    notice: Notice,
    *,
    title: str,
    content: str,
    type: str = Notice.Type.NORMAL,
    image_url: str | None = None,
) -> Notice:
    """기존 공지사항을 수정하고 수정 일시를 갱신합니다."""
    notice.title = title
    notice.content = content
    notice.type = type
    notice.image_url = image_url
    notice.updated_at = timezone.now()
    notice.save(update_fields=["title", "content", "type", "image_url", "updated_at"])
    return notice


@transaction.atomic
def delete_notice(notice: Notice) -> None:
    """공지사항을 논리 삭제(Soft Delete) 처리합니다."""
    notice.deleted_at = timezone.now()
    notice.save(update_fields=["deleted_at", "updated_at"])


def upload_notice_image(image: UploadedFile, *, request=None) -> str:
    """공지사항 첨부 이미지를 검증하고 저장한 뒤 접근 URL을 반환합니다.

    - 최대 파일 크기: 10MB (초과 시 FileSizeExceeded / 413)
    - 지원 확장자: JPG, JPEG, PNG, WebP (그 외 또는 손상 시 InvalidImageFile / 400)
    """
    if not image:
        raise InvalidImageFile(
            errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
        )

    # 1. 파일 크기 검증 (10MB)
    if image.size > MAX_IMAGE_SIZE:
        raise FileSizeExceeded()

    # 2. 파일 확장자 검증
    ext = os.path.splitext(image.name or "")[1].lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidImageFile(
            errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
        )

    # 3. MIME 타입 검증
    content_type = getattr(image, "content_type", None)
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise InvalidImageFile(
            errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
        )

    # 4. 이미지 무결성 및 실제 포맷 검증 (Pillow)
    try:
        image.seek(0)
        img = Image.open(image)
        img.verify()
        if (img.format or "").upper() not in ALLOWED_IMAGE_FORMATS:
            raise InvalidImageFile(
                errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
            )
        image.seek(0)
    except (UnidentifiedImageError, Exception) as exc:
        raise InvalidImageFile(
            errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
        ) from exc

    # 4. 고유 파일명 생성 및 저장 (notices/YYYYMMDD_uuid.ext)
    today_str = timezone.localdate().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:12]
    normalized_ext = "jpg" if ext in ("jpg", "jpeg") else ext
    filename = f"notices/{today_str}_{unique_suffix}.{normalized_ext}"

    saved_path = default_storage.save(filename, image)
    url = default_storage.url(saved_path)

    if request:
        return request.build_absolute_uri(url)
    return url
