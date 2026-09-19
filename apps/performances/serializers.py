"""공연 API 요청 및 응답 데이터 처리."""

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers


def to_local_iso(value):
    """날짜·시간을 한국 시각의 API 응답 형식으로 변환한다."""
    return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M:%S")


class PerformanceListQuerySerializer(serializers.Serializer):
    """타임테이블 조회 조건 검증."""

    date = serializers.DateField(required=False)

    def validate_date(self, value):
        start = settings.FESTIVAL_START_DATE
        end = settings.FESTIVAL_END_DATE

        if not (start <= value <= end):
            raise serializers.ValidationError(
                f"{start} ~ {end} 중에서 선택해주세요."
            )

        return value


def to_list_item(performance, *, is_live):
    """공연 목록 아이템으로 변환한다."""
    return {
        "performance_id": performance.pk,
        "team_name": performance.team_name,
        "affiliation": performance.affiliation,
        "image_url": performance.image_url,
        "start_at": to_local_iso(performance.start_at),
        "end_at": to_local_iso(performance.end_at),
        "is_live": is_live,
    }


def to_detail(performance):
    """공연 상세 응답으로 변환한다."""
    return {
        "performance_id": performance.pk,
        "team_name": performance.team_name,
        "affiliation": performance.affiliation,
        "description": performance.description,
        "image_url": performance.image_url,
        "festival_date": performance.festival_date,
        "start_at": to_local_iso(performance.start_at),
        "end_at": to_local_iso(performance.end_at),
        "songs": [
            {
                "song_id": song.pk,
                "title": song.title,
                "artist": song.artist,
                "sort_order": song.sort_order,
            }
            for song in performance.alive_songs
        ],
    }


class PerformanceListItemSerializer(serializers.Serializer):
    performance_id = serializers.IntegerField()
    team_name = serializers.CharField()
    affiliation = serializers.CharField(allow_null=True)
    image_url = serializers.URLField(allow_null=True)
    start_at = serializers.CharField(
        help_text="2026-09-29T16:00:00 (KST)"
    )
    end_at = serializers.CharField(
        help_text="2026-09-29T17:00:00 (KST)"
    )
    is_live = serializers.BooleanField()


class PerformanceListDataSerializer(serializers.Serializer):
    festival_date = serializers.DateField()
    server_time = serializers.CharField(
        help_text="2026-09-29T16:30:00 (KST)"
    )
    performances = PerformanceListItemSerializer(many=True)


class PerformanceListResponseSerializer(serializers.Serializer):
    """공연 타임테이블 조회 성공 응답."""

    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="PERFORMANCE_LIST_SUCCESS")
    message = serializers.CharField(default="공연 목록을 조회했습니다.")
    data = PerformanceListDataSerializer()


class SongSerializer(serializers.Serializer):
    song_id = serializers.IntegerField()
    title = serializers.CharField()
    artist = serializers.CharField(allow_null=True)
    sort_order = serializers.IntegerField()


class PerformanceDetailDataSerializer(serializers.Serializer):
    performance_id = serializers.IntegerField()
    team_name = serializers.CharField()
    affiliation = serializers.CharField(allow_null=True)
    description = serializers.CharField(allow_null=True)
    image_url = serializers.URLField(allow_null=True)
    festival_date = serializers.DateField()
    start_at = serializers.CharField(
        help_text="2026-09-29T16:00:00 (KST)"
    )
    end_at = serializers.CharField(
        help_text="2026-09-29T17:00:00 (KST)"
    )
    songs = SongSerializer(many=True)


class PerformanceDetailResponseSerializer(serializers.Serializer):
    """공연 상세 조회 성공 응답."""

    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="PERFORMANCE_DETAIL_SUCCESS")
    message = serializers.CharField(default="공연 정보를 조회했습니다.")
    data = PerformanceDetailDataSerializer()


class PerformanceNowDataSerializer(serializers.Serializer):
    server_time = serializers.CharField(
        help_text="2026-09-29T15:20:00 (KST)"
    )
    performances = PerformanceListItemSerializer(many=True)


class PerformanceNowResponseSerializer(serializers.Serializer):
    """지금 공연 중 조회 성공 응답."""

    success = serializers.BooleanField(default=True)
    code = serializers.CharField(default="PERFORMANCE_NOW_SUCCESS")
    message = serializers.CharField(default="현재 공연 정보를 조회했습니다.")
    data = PerformanceNowDataSerializer()