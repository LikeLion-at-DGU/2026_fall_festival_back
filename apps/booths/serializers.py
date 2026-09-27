"""Booths request and response serializers."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .constants import CATEGORY_CHIPS
from .models import Booth, BoothMenu, BoothOperation


# 장소 목록 카드. BoothOperation 행을 입력으로 받는다 (부스당 최대 1행)
class BoothListItemSerializer(serializers.Serializer):
    booth_id = serializers.IntegerField(source="booth.id")
    name = serializers.CharField(source="booth.name")
    subtitle = serializers.CharField(source="booth.subtitle")
    place_type = serializers.CharField(source="booth.place_type")
    category = serializers.CharField(source="booth.category")
    restroom_type = serializers.ChoiceField(
        source="booth.restroom_type",
        choices=Booth.RestroomType.choices,
        allow_null=True,
    )
    booth_size = serializers.ChoiceField(
        source="booth.booth_size",
        choices=Booth.BoothSize.choices,
        allow_null=True,
    )
    location_detail = serializers.CharField(source="booth.location_detail")
    directions = serializers.CharField(source="booth.directions")
    zone = serializers.CharField(source="booth.zone")
    map_x = serializers.FloatField(source="booth.map_x")
    map_y = serializers.FloatField(source="booth.map_y")
    map_elevation = serializers.FloatField(source="booth.map_elevation")
    rotation = serializers.FloatField(source="booth.rotation")
    placements = serializers.SerializerMethodField()
    thumbnail_url = serializers.CharField(source="booth.thumbnail_url")
    lantern_count = serializers.IntegerField(source="daily_lantern_count")
    has_my_lantern = serializers.SerializerMethodField()
    operation = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField)
    def get_has_my_lantern(self, obj):
        # selectors에서 annotate된 값. 비로그인 요청은 annotate가 없으므로 False
        return getattr(obj, "has_my_lantern", False)

    def get_placements(self, obj):
        return obj.placements or []

    def get_operation(self, obj):
        return {
            "open_at": obj.open_at.strftime("%H:%M"),
            "close_at": obj.close_at.strftime("%H:%M"),
        }


class BoothOperationSerializer(serializers.ModelSerializer):
    open_at = serializers.TimeField(format="%H:%M")
    close_at = serializers.TimeField(format="%H:%M")
    placements = serializers.SerializerMethodField()

    class Meta:
        model = BoothOperation
        fields = [
            "festival_date",
            "time_slot",
            "open_at",
            "close_at",
            "placements",
        ]

    def get_placements(self, obj):
        return obj.placements or []


class BoothMenuSerializer(serializers.ModelSerializer):
    menu_id = serializers.IntegerField(source="id")

    class Meta:
        model = BoothMenu
        fields = ["menu_id", "name", "price", "sort_order"]


class BoothDetailSerializer(serializers.ModelSerializer):
    booth_id = serializers.IntegerField(source="id")
    map_x = serializers.FloatField()
    map_y = serializers.FloatField()
    map_elevation = serializers.FloatField()
    rotation = serializers.FloatField()
    has_my_lantern = serializers.SerializerMethodField()
    operations = BoothOperationSerializer(many=True)
    menus = BoothMenuSerializer(many=True)

    class Meta:
        model = Booth
        fields = [
            "booth_id",
            "name",
            "subtitle",
            "place_type",
            "category",
            "restroom_type",
            "booth_size",
            "description",
            "zone",
            "location_detail",
            "map_x",
            "map_y",
            "map_elevation",
            "rotation",
            "thumbnail_url",
            "image_url",
            "entrance_fee",
            "event_description",
            "instagram_id",
            "has_reusable_container",
            "directions",
            "lantern_count",
            "has_my_lantern",
            "operations",
            "menus",
        ]

    @extend_schema_field(serializers.BooleanField)
    def get_has_my_lantern(self, obj):
        # selectors에서 annotate된 값. 비로그인 요청은 annotate가 없으므로 False
        return getattr(obj, "has_my_lantern", False)


# 검색 결과 카드. 목록 카드와 동일 구조 (operation만 없음)
class BoothSearchItemSerializer(serializers.ModelSerializer):
    booth_id = serializers.IntegerField(source="id")
    map_x = serializers.FloatField()
    map_y = serializers.FloatField()
    map_elevation = serializers.FloatField()
    rotation = serializers.FloatField()
    has_my_lantern = serializers.SerializerMethodField()
    lantern_count = serializers.IntegerField(source="daily_lantern_count")

    class Meta:
        model = Booth
        fields = [
            "booth_id",
            "name",
            "subtitle",
            "place_type",
            "category",
            "restroom_type",
            "booth_size",
            "location_detail",
            "directions",
            "zone",
            "map_x",
            "map_y",
            "map_elevation",
            "rotation",
            "thumbnail_url",
            "lantern_count",
            "has_my_lantern",
        ]

    @extend_schema_field(serializers.BooleanField)
    def get_has_my_lantern(self, obj):
        # selectors에서 annotate된 값. 비로그인 요청은 annotate가 없으므로 False
        return getattr(obj, "has_my_lantern", False)


# --- Swagger 문서화용 요청/응답 스키마 ---
# 아래 뷰들은 쿼리 파라미터를 직접(request.query_params) 검증하므로, 이 시리얼라이저들은
# 실제 검증 로직으로 쓰이지 않고 drf-spectacular가 스키마를 생성할 때만 참조된다.


class BoothListQuerySerializer(serializers.Serializer):
    date = serializers.DateField(
        required=False,
        help_text="조회할 축제 날짜. 미지정 시 서버 오늘(축제 기간 밖이면 2026-09-29)",
    )
    time_slot = serializers.ChoiceField(
        choices=BoothOperation.TimeSlot.choices,
        required=False,
        help_text="주간/야간. 미지정 시 서버 시각 기준(16:30 이전 DAY / 이후 NIGHT)",
    )
    category = serializers.ChoiceField(
        choices=CATEGORY_CHIPS, required=False, help_text="컬러칩 필터. 미지정 시 전체"
    )


class BoothDetailQuerySerializer(serializers.Serializer):
    date = serializers.DateField(
        required=False,
        help_text="has_my_lantern 계산 기준 날짜 (2026-09-29~2026-10-01). 미지정 시 서버 기본 날짜",
    )


class BoothSearchQuerySerializer(serializers.Serializer):
    keyword = serializers.CharField(required=True, max_length=50, help_text="검색어 (1~50자)")
    date = serializers.DateField(
        required=False,
        help_text=(
            "지정 시 그 날짜에 운영하는 부스만 검색 결과에 포함. "
            "미지정 시 검색 결과 범위는 날짜 무관 전체지만, "
            "lantern_count/has_my_lantern은 서버 기본 날짜 기준으로 계산됨"
        ),
    )
    time_slot = serializers.ChoiceField(
        choices=BoothOperation.TimeSlot.choices,
        required=False,
        help_text="주간/야간. date와 함께일 때만 사용 가능",
    )


class BoothListDataSerializer(serializers.Serializer):
    festival_date = serializers.CharField(help_text="적용된 조회 날짜 (YYYY-MM-DD)")
    time_slot = serializers.ChoiceField(
        choices=BoothOperation.TimeSlot.choices, help_text="적용된 시간대"
    )
    server_time = serializers.CharField(help_text="서버 현재 시각 (YYYY-MM-DDTHH:MM:SS)")
    total_count = serializers.IntegerField(help_text="조회된 부스 수")
    booths = BoothListItemSerializer(many=True, help_text="부스 목록 (등불 값은 위 날짜 기준)")


class BoothListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True, help_text="성공 여부 (True)")
    code = serializers.CharField(help_text="응답 코드 (BOOTH_LIST_SUCCESS)")
    message = serializers.CharField(help_text="응답 메시지 (장소 목록을 조회했습니다.)")
    data = BoothListDataSerializer(help_text="응답 데이터")


class BoothDetailResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True, help_text="성공 여부 (True)")
    code = serializers.CharField(help_text="응답 코드 (BOOTH_DETAIL_SUCCESS)")
    message = serializers.CharField(help_text="응답 메시지 (장소 정보를 조회했습니다.)")
    data = BoothDetailSerializer(
        help_text="응답 데이터 (has_my_lantern은 요청 date 기준, lantern_count는 전체 누적)"
    )


class BoothSearchDataSerializer(serializers.Serializer):
    keyword = serializers.CharField(help_text="검색어")
    total_count = serializers.IntegerField(help_text="검색된 부스 수")
    booths = BoothSearchItemSerializer(
        many=True, help_text="검색 결과 부스 목록 (등불 값은 요청 date 또는 서버 기본 날짜 기준)"
    )


class BoothSearchResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True, help_text="성공 여부 (True)")
    code = serializers.CharField(help_text="응답 코드 (BOOTH_SEARCH_SUCCESS)")
    message = serializers.CharField(help_text="응답 메시지 (장소를 검색했습니다.)")
    data = BoothSearchDataSerializer(help_text="응답 데이터")
