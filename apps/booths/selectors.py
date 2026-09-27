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
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.lanterns.models import Lantern

from .constants import BOOTH_CHIP
from .models import Booth, BoothMenu, BoothOperation


def _name_sort_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _my_lantern_exists(user, booth_ref, festival_date=None):
    # 해당 부스에 로그인 사용자의 삭제되지 않은 등불이 있는지 (서브쿼리)
    # festival_date를 주면 그 날짜 기준, 안 주면 기간 전체 기준으로 판단한다.
    lantern_filter = {
        "booth_id": OuterRef(booth_ref),
        "user": user,
        "deleted_at__isnull": True,
    }
    if festival_date is not None:
        lantern_filter["festival_date"] = festival_date
    return Exists(Lantern.objects.filter(**lantern_filter))


def _lantern_count_on(booth_ref, festival_date):
    # 특정 날짜 기준 해당 부스의 삭제되지 않은 등불 개수 (상관 서브쿼리)
    return Coalesce(
        Subquery(
            Lantern.objects.filter(
                booth_id=OuterRef(booth_ref),
                festival_date=festival_date,
                deleted_at__isnull=True,
            )
            .values("booth_id")
            .annotate(count=Count("id"))
            .values("count"),
            output_field=IntegerField(),
        ),
        0,
    )


def booth_operations_on(festival_date, time_slot, category=None, user=None):
    queryset = BoothOperation.objects.filter(
        festival_date=festival_date,
        deleted_at__isnull=True,
        booth__deleted_at__isnull=True,
    ).select_related("booth")

    fixed_category = category in {
        Booth.Category.ALCOHOL,
        Booth.Category.TOILET,
        Booth.Category.ECO,
    }

    if category == BOOTH_CHIP:
        booth_categories = [Booth.Category.ETC, Booth.Category.COLLAB]
        if time_slot == BoothOperation.TimeSlot.NIGHT:
            booth_categories.append(Booth.Category.ALCOHOL)

        queryset = (
            queryset.filter(time_slot=time_slot)
            .filter(
                Q(
                    booth__place_type=Booth.PlaceType.BOOTH,
                    booth__category__in=booth_categories,
                )
                | Q(
                    booth__place_type=Booth.PlaceType.FACILITY,
                    booth__category=Booth.Category.ETC,
                )
            )
            .annotate(
                collab_order=Case(
                    When(booth__category=Booth.Category.COLLAB, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
        )
    elif category == Booth.Category.ALCOHOL:
        queryset = queryset.filter(
            booth__place_type=Booth.PlaceType.FACILITY,
            booth__category=Booth.Category.ALCOHOL,
        )
    elif category == Booth.Category.TOILET:
        queryset = queryset.filter(
            booth__place_type=Booth.PlaceType.FACILITY,
            booth__category=Booth.Category.TOILET,
        )
    elif category == Booth.Category.ECO:
        queryset = queryset.filter(booth__category=Booth.Category.ECO)
    else:
        queryset = queryset.filter(time_slot=time_slot)

    if user is not None:
        queryset = queryset.annotate(
            has_my_lantern=_my_lantern_exists(user, "booth_id", festival_date=festival_date)
        )
    queryset = queryset.annotate(daily_lantern_count=_lantern_count_on("booth_id", festival_date))

    operations = list(queryset)

    if fixed_category:
        operations.sort(
            key=lambda operation: (
                operation.booth_id,
                operation.time_slot != time_slot,
                operation.id,
            )
        )

        unique_operations = {}
        for operation in operations:
            unique_operations.setdefault(operation.booth_id, operation)

        operations = list(unique_operations.values())

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


def booth_detail(booth_id, user=None, festival_date=None):
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
        queryset = queryset.annotate(
            has_my_lantern=_my_lantern_exists(user, "pk", festival_date=festival_date)
        )
    return queryset.first()


def booth_search(
    keyword, operation_filter_date=None, time_slot=None, user=None, *, lantern_scope_date
):
    # operation_filter_date: 검색 결과 범위(어떤 부스를 보여줄지)에만 쓰인다.
    # None이면 날짜 무관 전체.
    # lantern_scope_date: lantern_count/has_my_lantern 계산 기준 날짜.
    # 호출부(뷰)가 항상 실제 날짜로 확정해서 넘긴다
    # (date 미지정 요청이어도 서버 기본 날짜로 계산되어야 하기 때문).
    match = (
        Q(name__icontains=keyword)
        | Q(subtitle__icontains=keyword)
        | Q(location_detail__icontains=keyword)
        | Q(description__icontains=keyword)
        | Q(menus__name__icontains=keyword, menus__deleted_at__isnull=True)
    )
    queryset = Booth.objects.filter(match, deleted_at__isnull=True)

    if operation_filter_date:
        operating = Q(
            operations__festival_date=operation_filter_date, operations__deleted_at__isnull=True
        )
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
        queryset = queryset.annotate(
            has_my_lantern=_my_lantern_exists(user, "pk", festival_date=lantern_scope_date)
        )
    queryset = queryset.annotate(daily_lantern_count=_lantern_count_on("pk", lantern_scope_date))

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
