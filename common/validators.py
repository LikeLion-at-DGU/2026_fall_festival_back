"""공통 파일 검증 로직."""

import os

from PIL import Image, UnidentifiedImageError

from .exceptions import FileTooLarge, UnsupportedFileType


# 실제 이미지 포맷별 허용 확장자
IMAGE_FORMAT_EXTENSIONS = {
    "JPEG": {"jpg", "jpeg"},
    "PNG": {"png"},
    "WEBP": {"webp"},
}

# 저장 시 사용할 대표 확장자
IMAGE_FORMAT_CANONICAL_EXTENSION = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


def validate_image_upload(uploaded_file, *, allowed_extensions, max_bytes):
    """이미지 확장자, 용량, 실제 포맷을 검증한다."""

    extension = os.path.splitext(uploaded_file.name)[1].lower().lstrip(".")

    if extension not in allowed_extensions:
        raise UnsupportedFileType()

    if uploaded_file.size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise FileTooLarge(message=f"이미지 용량은 {max_mb}MB 이하여야 합니다.")

    try:
        with Image.open(uploaded_file) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedFileType() from exc
    finally:
        # 검증 후 저장할 수 있도록 파일 포인터 초기화
        uploaded_file.seek(0)

    if image_format not in IMAGE_FORMAT_EXTENSIONS:
        raise UnsupportedFileType()

    if extension not in IMAGE_FORMAT_EXTENSIONS[image_format]:
        raise UnsupportedFileType()

    # JPEG 확장자는 jpg로 통일
    return IMAGE_FORMAT_CANONICAL_EXTENSION[image_format]