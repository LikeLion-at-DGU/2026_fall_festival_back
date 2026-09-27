"""Booths request and response serializers."""

from rest_framework import serializers

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
    lantern_count = serializers.SerializerMethodField()

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

    def get_has_my_lantern(self, obj):
        # selectors에서 annotate된 값. 비로그인 요청은 annotate가 없으므로 False
        return getattr(obj, "has_my_lantern", False)

    def get_lantern_count(self, obj):
        # date 지정 검색은 selectors가 daily_lantern_count를 annotate한다.
        # date 미지정(날짜 무관 전체 검색)일 땐 annotate가 없으므로 누적값으로 대체한다.
        daily_count = getattr(obj, "daily_lantern_count", None)
        return daily_count if daily_count is not None else obj.lantern_count
