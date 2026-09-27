"""Read-only booths queries."""

import unicodedata

from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Value,
    When,
)

from apps.lanterns.models import Lantern

from .constants import BOOTH_CHIP, BOOTH_CHIP_CATEGORIES
from .models import Booth, BoothMenu, BoothOperation


def _name_sort_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _my_lantern_exists(user, booth_ref):
    # 해당 부스에 로그인 사용자의 삭제되지 않은 등불이 있는지 (서브쿼리)
    return Exists(
        Lantern.objects.filter(booth_id=OuterRef(booth_ref), user=user, deleted_at__isnull=True)
    )


def booth_operations_on(festival_date, time_slot, category=None, user=None):
    # UNIQUE(booth, festival_date, time_slot) 제약으로 부스당 최대 1행 보장
    queryset = BoothOperation.objects.filter(
        festival_date=festival_date,
        time_slot=time_slot,
        deleted_at__isnull=True,
        booth__deleted_at__isnull=True,
    ).select_related("booth")

    # '부스' 칩 — 협업 부스(ㄱㄴㄷ순) 먼저, 그 아래 일반 부스(ㄱㄴㄷ순)
    if category == BOOTH_CHIP:
        queryset = (
            queryset.filter(booth__category__in=BOOTH_CHIP_CATEGORIES)
            .annotate(
                collab_order=Case(
                    When(booth__category=Booth.Category.COLLAB, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("collab_order", "booth__name")
        )
    else:
        # 그 외 — 이름 ㄱㄴㄷ순 (등불 인기 정렬은 부스 랭킹 API가 담당)
        if category:
            queryset = queryset.filter(booth__category=category)
        queryset = queryset.order_by("booth__name")

    if user is not None:
        queryset = queryset.annotate(has_my_lantern=_my_lantern_exists(user, "booth_id"))

    operations = list(queryset)

    if category == BOOTH_CHIP:
        return sorted(
            operations,
            key=lambda operation: (
                operation.collab_order,
                _name_sort_key(operation.booth.name),
                operation.booth_id,
            ),
        )

    return sorted(
        operations,
        key=lambda operation: (
            _name_sort_key(operation.booth.name),
            operation.booth_id,
        ),
    )


def booth_detail(booth_id, user=None):
    queryset = Booth.objects.filter(pk=booth_id, deleted_at__isnull=True).prefetch_related(
        Prefetch(
            "operations",
            queryset=BoothOperation.objects.filter(deleted_at__isnull=True).order_by(
                "festival_date", "time_slot"
            ),
        ),
        Prefetch(
            "menus",
            queryset=BoothMenu.objects.filter(deleted_at__isnull=True).order_by("sort_order"),
        ),
    )
    if user is not None:
        queryset = queryset.annotate(has_my_lantern=_my_lantern_exists(user, "pk"))
    return queryset.first()


def booth_search(keyword, festival_date=None, time_slot=None, user=None):
    # 부스명/소속/위치/소개/메뉴명 부분 일치 OR 검색. 메뉴 매칭은 중복 제거
    match = (
        Q(name__icontains=keyword)
        | Q(subtitle__icontains=keyword)
        | Q(location_detail__icontains=keyword)
        | Q(description__icontains=keyword)
        | Q(menus__name__icontains=keyword, menus__deleted_at__isnull=True)
    )
    queryset = Booth.objects.filter(match, deleted_at__isnull=True)

    if festival_date:
        operating = Q(operations__festival_date=festival_date, operations__deleted_at__isnull=True)
        if time_slot:
            operating &= Q(operations__time_slot=time_slot)
        queryset = queryset.filter(operating)

    # 정렬: 부스명 정확 일치 → 부스명 부분 일치 → 그 외, 같은 그룹 안에서는 이름 ㄱㄴㄷ순
    queryset = queryset.annotate(
        match_rank=Case(
            When(name__iexact=keyword, then=Value(0)),
            When(name__icontains=keyword, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    )
    if user is not None:
        queryset = queryset.annotate(has_my_lantern=_my_lantern_exists(user, "pk"))

    booths = list(queryset.distinct())

    return sorted(
        booths,
        key=lambda booth: (
            booth.match_rank,
            _name_sort_key(booth.name),
            booth.id,
        ),
    )


# 부스 랭킹은 홈 화면에서 자주 조회되는 값이라 짧은 TTL로 캐싱한다.
# 등불 등록/삭제 시점에 캐시를 직접 무효화하지 않고 TTL 만료로만 갱신하므로,
# 최대 RANKING_CACHE_TTL초 동안은 방금 등록/삭제된 등불이 랭킹에 반영되지 않을 수 있다.
RANKING_CACHE_TTL = 5


def booth_ranking(festival_date, limit):
    cache_key = f"booth_ranking:{festival_date.isoformat()}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    booths = list(
        Booth.objects.filter(
            place_type=Booth.PlaceType.BOOTH,
            deleted_at__isnull=True,
        ).annotate(
            daily_lantern_count=Count(
                "lanterns",
                filter=Q(
                    lanterns__festival_date=festival_date,
                    lanterns__deleted_at__isnull=True,
                ),
            )
        )
    )

    result = sorted(
        booths,
        key=lambda booth: (
            -booth.daily_lantern_count,
            _name_sort_key(booth.name),
            booth.id,
        ),
    )[:limit]

    cache.set(cache_key, result, timeout=RANKING_CACHE_TTL)
    return result


def total_lantern_count(festival_date):
    cache_key = f"booth_total_lantern_count:{festival_date.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    total = Lantern.objects.filter(
        festival_date=festival_date,
        deleted_at__isnull=True,
        booth__place_type=Booth.PlaceType.BOOTH,
        booth__deleted_at__isnull=True,
    ).count()

    cache.set(cache_key, total, timeout=RANKING_CACHE_TTL)
    return total
