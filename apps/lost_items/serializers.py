"""분실물 API 요청/응답 데이터 처리.

- 목록 조회 조건 검증
- 등록/수정 요청 검증
- 응답 데이터 변환 및 Swagger 스키마 정의
"""

from django.conf import settings
from rest_framework import serializers

from common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

from .selectors import thumbnail_url, top_keywords


class LostItemListQuerySerializer(serializers.Serializer):
    found_date = serializers.DateField(required=False)
    page = serializers.IntegerField(required=False, min_value=0, default=0)
    size = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )


class LostItemWriteSerializer(serializers.Serializer):
    """등록(POST)과 수정(PUT) 요청 바디 검증용.

    명세서에 "수정은 등록과 동일 스키마"라고 나와 있고, 실제로도 필드·검증
    로직이 똑같아서 하나로 합쳤다. (등록만 있을 때는 LostItemCreateSerializer
    라는 이름으로 따로 뒀었는데, PUT이 진짜로 똑같이 쓰게 되면서 이름을
    이렇게 바꿨다.)
    """

    title = serializers.CharField(max_length=100, allow_blank=False, trim_whitespace=True)
    found_date = serializers.DateField()
    image_urls = serializers.ListField(
        child=serializers.URLField(max_length=500), required=False, default=list
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=30, allow_blank=False, trim_whitespace=True),
        allow_empty=False,
    )

    def validate_found_date(self, value):
        # 축제 기간(9/29~10/1) 밖의 날짜면 여기서 막는다.
        start, end = settings.FESTIVAL_START_DATE, settings.FESTIVAL_END_DATE
        if not (start <= value <= end):
            raise serializers.ValidationError(f"{start} ~ {end} 중에서 선택해주세요.")
        return value

    def validate_tags(self, value):
        # "#지갑"과 "지갑"을 같은 키워드로 취급하고, 등장 순서를 유지한 채 중복만 없앤다.
        seen, deduplicated = set(), []
        for keyword in value:
            normalized = keyword.lstrip("#").strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduplicated.append(normalized)
        if not deduplicated:
            raise serializers.ValidationError("키워드칩을 1개 이상 입력해주세요.")
        return deduplicated


def to_list_item(lost_item):
    return {
        "lost_item_id": lost_item.pk,
        "title": lost_item.title,
        "found_date": lost_item.found_date,
        "thumbnail_url": thumbnail_url(lost_item),
        "tags": top_keywords(lost_item),
        "created_at": lost_item.created_at,
    }


def to_detail(lost_item):
    return {
        "lost_item_id": lost_item.pk,
        "title": lost_item.title,
        "found_date": lost_item.found_date,
        "images": [
            {"image_id": image.pk, "image_url": image.image_url, "sort_order": image.sort_order}
            for image in lost_item.alive_images
        ],
        "tags": [
            {"tag_id": tag.pk, "keyword": tag.keyword, "sort_order": tag.sort_order}
            for tag in lost_item.alive_tags
        ],
        "created_at": lost_item.created_at,
        "updated_at": lost_item.updated_at,
    }


class LostItemListItemSerializer(serializers.Serializer):
    lost_item_id = serializers.IntegerField()
    title = serializers.CharField()
    found_date = serializers.DateField()
    thumbnail_url = serializers.URLField(allow_null=True)
    tags = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class LostItemListDataSerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    page = serializers.IntegerField()
    size = serializers.IntegerField()
    has_next = serializers.BooleanField()
    items = LostItemListItemSerializer(many=True)


class LostItemListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_LIST_SUCCESS")
    message = serializers.CharField(default="분실물 목록을 조회했습니다.")
    data = LostItemListDataSerializer()


class LostItemImageSerializer(serializers.Serializer):
    image_id = serializers.IntegerField()
    image_url = serializers.URLField()
    sort_order = serializers.IntegerField()


class LostItemTagSerializer(serializers.Serializer):
    tag_id = serializers.IntegerField()
    keyword = serializers.CharField()
    sort_order = serializers.IntegerField()


class LostItemDetailDataSerializer(serializers.Serializer):
    lost_item_id = serializers.IntegerField()
    title = serializers.CharField()
    found_date = serializers.DateField()
    images = LostItemImageSerializer(many=True)
    tags = LostItemTagSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField(allow_null=True)


class LostItemDetailResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_DETAIL_SUCCESS")
    message = serializers.CharField(default="분실물 정보를 조회했습니다.")
    data = LostItemDetailDataSerializer()


class LostItemIdDataSerializer(serializers.Serializer):
    lost_item_id = serializers.IntegerField()


class LostItemIdResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_CREATE_SUCCESS")
    message = serializers.CharField(default="분실물을 등록했습니다.")
    data = LostItemIdDataSerializer()


class LostItemUpdateResponseSerializer(serializers.Serializer):
    # PUT의 응답 본문은 상세 조회(GET)와 모양이 같지만, code/message 기본값이
    # 다르다. LostItemDetailResponseSerializer를 그대로 쓰면 Swagger 문서에
    # "LOST_ITEM_DETAIL_SUCCESS"가 잘못 표시되므로 따로 둔다.
    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_UPDATE_SUCCESS")
    message = serializers.CharField(default="분실물 정보를 수정했습니다.")
    data = LostItemDetailDataSerializer()


class LostItemDeleteDataSerializer(serializers.Serializer):
    lost_item_id = serializers.IntegerField()
    deleted_at = serializers.DateTimeField()


class LostItemDeleteResponseSerializer(serializers.Serializer):
    """분실물 삭제 성공 응답."""

    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_DELETE_SUCCESS")
    message = serializers.CharField(default="분실물을 삭제했습니다.")
    data = LostItemDeleteDataSerializer()


class UserLostItemListQuerySerializer(serializers.Serializer):
    found_date = serializers.DateField(
        required=False, error_messages={"invalid": "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)"}
    )
    keyword = serializers.CharField(required=False, allow_blank=True, max_length=100)
    page = serializers.IntegerField(required=False, min_value=0, default=0)
    size = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )


def to_user_detail(lost_item):
    return {
        "lost_item_id": lost_item.pk,
        "title": lost_item.title,
        "found_date": lost_item.found_date,
        "images": [
            {
                "image_id": image.pk,
                "image_url": image.image_url,
                "sort_order": image.sort_order,
            }
            for image in getattr(
                lost_item, "alive_images", lost_item.images.filter(deleted_at__isnull=True)
            )
        ],
        "tags": [
            tag.keyword
            for tag in getattr(
                lost_item, "alive_tags", lost_item.tags.filter(deleted_at__isnull=True)
            )
        ],
        "created_at": lost_item.created_at,
    }


class UserLostItemDetailDataSerializer(serializers.Serializer):
    lost_item_id = serializers.IntegerField()
    title = serializers.CharField()
    found_date = serializers.DateField()
    images = LostItemImageSerializer(many=True)
    tags = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class UserLostItemDetailResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_DETAIL_SUCCESS")
    message = serializers.CharField(default="분실물 상세 정보를 조회했습니다.")
    data = UserLostItemDetailDataSerializer()
    
    
class LostItemImageUploadRequestSerializer(serializers.Serializer):
    """분실물 이미지 업로드 요청."""

    file = serializers.FileField()


class LostItemImageUploadDataSerializer(serializers.Serializer):
    """업로드 이미지 정보."""

    image_url = serializers.URLField()


class LostItemImageUploadResponseSerializer(serializers.Serializer):
    """분실물 이미지 업로드 성공 응답."""

    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="LOST_ITEM_IMAGE_UPLOAD_SUCCESS")
    message = serializers.CharField(default="이미지를 업로드했습니다.")
    data = LostItemImageUploadDataSerializer()