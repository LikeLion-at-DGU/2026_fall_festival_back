"""공연 조회 로직."""

from django.db.models import Prefetch

from .models import Performance, Song


def _alive_songs():
    """삭제되지 않은 셋리스트를 순서대로 조회한다."""
    return Prefetch(
        "songs",
        queryset=Song.objects.alive().order_by("sort_order", "song_id"),
        to_attr="alive_songs",
    )


def list_performances_on(festival_date):
    """해당 날짜의 공연을 시작 시간순으로 조회한다."""
    return (
        Performance.objects.alive()
        .filter(festival_date=festival_date)
        .order_by("start_at", "performance_id")
    )


def get_performance(performance_id):
    """공연 상세 정보를 조회한다."""
    return (
        Performance.objects.alive()
        .prefetch_related(_alive_songs())
        .filter(pk=performance_id)
        .first()
    )


def list_live(now):
    """현재 진행 중인 공연을 조회한다."""
    return list(
        Performance.objects.alive()
        .filter(start_at__lte=now, end_at__gte=now)
        .order_by("start_at", "performance_id")
    )


def list_upcoming_on(festival_date, now, limit):
    """해당 날짜의 예정 공연을 조회한다."""
    return list(
        Performance.objects.alive()
        .filter(festival_date=festival_date, start_at__gt=now)
        .order_by("start_at", "performance_id")[:limit]
    )