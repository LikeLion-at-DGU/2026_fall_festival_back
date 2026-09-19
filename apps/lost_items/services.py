"""분실물 등록, 수정, 삭제 및 이미지 저장 로직."""

import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from common.validators import validate_image_upload

from .models import LostItem, LostItemImage, LostItemTag


# 업로드 이미지 저장 경로
IMAGE_UPLOAD_DIR = "lost-items"


@transaction.atomic
def create_lost_item(*, title, found_date, image_urls, tags, admin_id=None):
    lost_item = LostItem.objects.create(
        title=title,
        found_date=found_date,
        created_by_admin_id=admin_id,
    )
    LostItemImage.objects.bulk_create(
        LostItemImage(lost_item=lost_item, image_url=url, sort_order=index)
        for index, url in enumerate(image_urls, start=1)
    )
    LostItemTag.objects.bulk_create(
        LostItemTag(lost_item=lost_item, keyword=keyword, sort_order=index)
        for index, keyword in enumerate(tags, start=1)
    )
    return lost_item


@transaction.atomic
def update_lost_item(lost_item, *, title, found_date, image_urls, tags):
    """분실물 정보를 수정하고 이미지·태그를 전체 교체한다."""
    now = timezone.now()

    lost_item.title = title
    lost_item.found_date = found_date
    lost_item.updated_at = now
    lost_item.save(update_fields=["title", "found_date", "updated_at"])

    lost_item.images.alive().soft_delete(now)
    lost_item.tags.alive().soft_delete(now)

    LostItemImage.objects.bulk_create(
        LostItemImage(lost_item=lost_item, image_url=url, sort_order=index)
        for index, url in enumerate(image_urls, start=1)
    )
    LostItemTag.objects.bulk_create(
        LostItemTag(lost_item=lost_item, keyword=keyword, sort_order=index)
        for index, keyword in enumerate(tags, start=1)
    )
    return lost_item


@transaction.atomic
def delete_lost_item(lost_item):
    """분실물과 그 아래 이미지·태그를 같은 시각으로 Soft Delete한다."""
    now = timezone.now()
    lost_item.images.alive().soft_delete(now)
    lost_item.tags.alive().soft_delete(now)
    lost_item.deleted_at = now
    lost_item.save(update_fields=["deleted_at"])
    return now

def store_image(uploaded_file):
    """이미지를 검증하고 저장한 뒤 URL을 반환한다."""

    extension = validate_image_upload(
        uploaded_file,
        allowed_extensions=settings.LOST_ITEM_IMAGE_EXTENSIONS,
        max_bytes=settings.LOST_ITEM_IMAGE_MAX_BYTES,
    )

    # 파일명 충돌 방지를 위해 UUID 사용
    filename = f"{uuid.uuid4().hex}.{extension}"
    relative_path = f"{IMAGE_UPLOAD_DIR}/{filename}"

    saved_path = default_storage.save(relative_path, uploaded_file)

    return default_storage.url(saved_path)