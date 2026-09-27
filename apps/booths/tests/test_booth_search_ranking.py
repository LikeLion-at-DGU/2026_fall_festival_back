"""Booth search and ranking API tests."""

from datetime import date, time

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booths.models import Booth, BoothMenu, BoothOperation
from apps.lanterns.models import Lantern

DATE_1 = date(2026, 9, 29)
DATE_2 = date(2026, 9, 30)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def search_booths(db):
    exact = Booth.objects.create(
        name="멋사",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )
    partial = Booth.objects.create(
        name="멋사 주점",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        booth_size=Booth.BoothSize.BIG,
    )
    by_description = Booth.objects.create(
        name="가나다 부스",
        description="멋사가 운영하는 부스입니다",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )
    by_menu = Booth.objects.create(
        name="라면 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )
    Booth.objects.create(
        name="무관 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )

    # 매칭 메뉴 2개 → 중복 제거(DISTINCT) 검증용
    BoothMenu.objects.create(
        booth=by_menu,
        name="멋사라면",
        price=5000,
        sort_order=1,
    )
    BoothMenu.objects.create(
        booth=by_menu,
        name="멋사김밥",
        price=3000,
        sort_order=2,
    )

    # 운영 정보는 partial에만 → date 필터 검증용
    BoothOperation.objects.create(
        booth=partial,
        festival_date=DATE_1,
        time_slot=BoothOperation.TimeSlot.NIGHT,
        open_at=time(17, 30),
        close_at=time(22, 0),
    )

    return {
        "exact": exact,
        "partial": partial,
        "by_description": by_description,
        "by_menu": by_menu,
    }


@pytest.mark.django_db
def test_search_requires_keyword(client, search_booths):
    response = client.get("/api/booths/search/")
    assert response.status_code == 400
    assert response.json()["message"] == "검색어를 입력해주세요."

    response = client.get("/api/booths/search/", {"keyword": "   "})
    assert response.status_code == 400


@pytest.mark.django_db
def test_search_orders_exact_then_partial_then_others(client, search_booths):
    response = client.get(
        "/api/booths/search/",
        {"keyword": "멋사"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["code"] == "BOOTH_SEARCH_SUCCESS"

    names = [item["name"] for item in body["data"]["booths"]]

    # 정확 일치 → 이름 부분 일치 → 그 외(소개/메뉴 매칭, 이름 ㄱㄴㄷ순)
    assert names == [
        "멋사",
        "멋사 주점",
        "가나다 부스",
        "라면 부스",
    ]
    assert body["data"]["total_count"] == 4
    assert body["data"]["booths"][0]["has_my_lantern"] is False

    partial_item = next(item for item in body["data"]["booths"] if item["name"] == "멋사 주점")
    assert partial_item["booth_size"] == "BIG"


@pytest.mark.django_db
def test_search_same_rank_uses_deterministic_name_order(client):
    names = [
        "빗썸",
        "만화얼",
        "상쾌환",
        "인캐쳐",
        "축기단",
        "글로벌 홍보대사 디그램",
        "인액터스",
        "Lotus",
    ]

    for name in names:
        Booth.objects.create(
            name=name,
            description="정렬검증 대상",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
        )

    response = client.get(
        "/api/booths/search/",
        {"keyword": "정렬검증"},
    )

    assert response.status_code == 200

    returned_names = [item["name"] for item in response.json()["data"]["booths"]]

    assert returned_names == [
        "Lotus",
        "글로벌 홍보대사 디그램",
        "만화얼",
        "빗썸",
        "상쾌환",
        "인액터스",
        "인캐쳐",
        "축기단",
    ]


@pytest.mark.django_db
def test_search_matches_menu_without_duplicates(client, search_booths):
    response = client.get(
        "/api/booths/search/",
        {"keyword": "멋사라면"},
    )

    names = [item["name"] for item in response.json()["data"]["booths"]]

    assert names == ["라면 부스"]


@pytest.mark.django_db
def test_search_filters_by_operating_date(client, search_booths):
    response = client.get(
        "/api/booths/search/",
        {
            "keyword": "멋사",
            "date": "2026-09-29",
            "time_slot": "NIGHT",
        },
    )

    names = [item["name"] for item in response.json()["data"]["booths"]]

    assert names == ["멋사 주점"]


@pytest.mark.django_db
def test_search_rejects_too_long_keyword(client, search_booths):
    response = client.get(
        "/api/booths/search/",
        {"keyword": "가" * 51},
    )

    assert response.status_code == 400
    assert response.json()["errors"]["keyword"] == "50자 이하로 입력해주세요."


@pytest.fixture
def ranking_booths(db):
    gaon = Booth.objects.create(
        name="가온 주점",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        lantern_count=32,
    )
    nara = Booth.objects.create(
        name="나래 주점",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ALCOHOL,
        lantern_count=32,
    )
    dasom = Booth.objects.create(
        name="다솜 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        lantern_count=30,
    )
    facility = Booth.objects.create(
        name="명진관 화장실",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
        lantern_count=99,
    )

    next_kakao_id = 910000

    def add_lantern(booth, festival_date, *, deleted=False):
        nonlocal next_kakao_id
        next_kakao_id += 1

        user = User.objects.create(
            kakao_id=next_kakao_id,
            nickname=f"랭킹사용자{next_kakao_id}",
        )

        return Lantern.objects.create(
            user=user,
            booth=booth,
            message="응원합니다",
            festival_date=festival_date,
            deleted_at=timezone.now() if deleted else None,
            deleted_by=Lantern.DeletedBy.USER if deleted else None,
        )

    # 9월 29일: 가온 2개, 나래 2개, 다솜 1개
    add_lantern(gaon, DATE_1)
    add_lantern(gaon, DATE_1)
    add_lantern(nara, DATE_1)
    add_lantern(nara, DATE_1)
    add_lantern(dasom, DATE_1)

    # 9월 30일: 다솜 3개
    add_lantern(dasom, DATE_2)
    add_lantern(dasom, DATE_2)
    add_lantern(dasom, DATE_2)

    # 삭제된 등불은 9월 29일 랭킹과 합계에서 제외
    add_lantern(dasom, DATE_1, deleted=True)

    # 시설의 등불도 부스 랭킹과 합계에서 제외
    add_lantern(facility, DATE_1)
    add_lantern(facility, DATE_1)
    add_lantern(facility, DATE_1)

    return {
        "gaon": gaon,
        "nara": nara,
        "dasom": dasom,
        "facility": facility,
        "add_lantern": add_lantern,
    }


@pytest.mark.django_db
def test_ranking_uses_selected_date_and_ties_share_rank(
    client,
    ranking_booths,
):
    response = client.get(
        "/api/booths/ranking/",
        {"date": "2026-09-29"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["code"] == "BOOTH_RANKING_SUCCESS"
    assert body["data"]["festival_date"] == "2026-09-29"

    ranking = body["data"]["ranking"]

    assert [
        (
            item["rank"],
            item["name"],
            item["lantern_count"],
        )
        for item in ranking
    ] == [
        (1, "가온 주점", 2),
        (1, "나래 주점", 2),
        (3, "다솜 부스", 1),
    ]

    # 삭제된 등불, 다른 날짜의 등불, 시설의 등불은 제외
    assert body["data"]["total_lantern_count"] == 5


@pytest.mark.django_db
def test_ranking_separates_lanterns_by_date(client, ranking_booths):
    response = client.get(
        "/api/booths/ranking/",
        {"date": "2026-09-30"},
    )

    assert response.status_code == 200

    body = response.json()
    ranking = body["data"]["ranking"]

    assert body["data"]["festival_date"] == "2026-09-30"
    assert ranking[0]["name"] == "다솜 부스"
    assert ranking[0]["lantern_count"] == 3
    assert body["data"]["total_lantern_count"] == 3


@pytest.mark.django_db
def test_ranking_excludes_facilities(client, ranking_booths):
    response = client.get(
        "/api/booths/ranking/",
        {"date": "2026-09-29"},
    )

    names = [item["name"] for item in response.json()["data"]["ranking"]]

    assert "명진관 화장실" not in names


@pytest.mark.django_db
def test_ranking_respects_limit(client, ranking_booths):
    response = client.get(
        "/api/booths/ranking/",
        {
            "date": "2026-09-29",
            "limit": "2",
        },
    )

    assert len(response.json()["data"]["ranking"]) == 2


@pytest.mark.django_db
def test_ranking_rejects_invalid_limit(client, ranking_booths):
    for bad in ["0", "21", "abc"]:
        response = client.get(
            "/api/booths/ranking/",
            {
                "date": "2026-09-29",
                "limit": bad,
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"]["limit"] == "1~20 사이의 정수로 입력해주세요."


@pytest.mark.django_db
def test_ranking_rejects_invalid_date(client, ranking_booths):
    response = client.get(
        "/api/booths/ranking/",
        {"date": "2026/09/29"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"

    response = client.get(
        "/api/booths/ranking/",
        {"date": "2026-10-05"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_FESTIVAL_DATE"


@pytest.mark.django_db
def test_ranking_caches_query_between_requests(
    client,
    ranking_booths,
    django_assert_num_queries,
):
    params = {"date": "2026-09-29"}

    first = client.get("/api/booths/ranking/", params)
    assert first.status_code == 200

    # 같은 날짜의 랭킹과 합계가 모두 캐시되었으므로 DB 조회가 발생하지 않는다.
    with django_assert_num_queries(0):
        second = client.get("/api/booths/ranking/", params)

    assert second.status_code == 200
    assert second.json()["data"] == first.json()["data"]


@pytest.mark.django_db
def test_ranking_cache_is_separated_by_date(client, ranking_booths):
    date_1_response = client.get(
        "/api/booths/ranking/",
        {
            "date": "2026-09-29",
            "limit": "1",
        },
    )
    date_2_response = client.get(
        "/api/booths/ranking/",
        {
            "date": "2026-09-30",
            "limit": "1",
        },
    )

    assert date_1_response.json()["data"]["ranking"][0]["name"] == "가온 주점"
    assert date_2_response.json()["data"]["ranking"][0]["name"] == "다솜 부스"


@pytest.mark.django_db
def test_ranking_reflects_lantern_change_only_after_cache_cleared(
    client,
    ranking_booths,
):
    params = {
        "date": "2026-09-29",
        "limit": "1",
    }

    first = client.get("/api/booths/ranking/", params)
    assert first.json()["data"]["ranking"][0]["name"] == "가온 주점"

    # 다솜의 당일 등불을 1개에서 3개로 늘린다.
    ranking_booths["add_lantern"](
        ranking_booths["dasom"],
        DATE_1,
    )
    ranking_booths["add_lantern"](
        ranking_booths["dasom"],
        DATE_1,
    )

    # 캐시가 유지되는 동안에는 기존 결과를 반환한다.
    stale = client.get("/api/booths/ranking/", params)
    assert stale.json()["data"]["ranking"][0]["name"] == "가온 주점"

    cache.clear()

    # 캐시를 비우면 실제 Lantern 데이터를 다시 집계한다.
    fresh = client.get("/api/booths/ranking/", params)
    assert fresh.json()["data"]["ranking"][0]["name"] == "다솜 부스"
    assert fresh.json()["data"]["ranking"][0]["lantern_count"] == 3


@pytest.mark.django_db
def test_search_rejects_time_slot_without_date(client, search_booths):
    response = client.get(
        "/api/booths/search/",
        {
            "keyword": "멋사",
            "time_slot": "NIGHT",
        },
    )

    assert response.status_code == 400
    assert response.json()["errors"]["time_slot"] == "time_slot은 date와 함께 사용해야 합니다."


@pytest.mark.django_db
def test_search_marks_my_lantern(
    auth_client,
    me,
    search_booths,
):
    Lantern.objects.create(
        user=me,
        booth=search_booths["partial"],
        message="화이팅",
        festival_date=DATE_1,
    )

    response = auth_client.get(
        "/api/booths/search/",
        {"keyword": "멋사"},
    )

    flags = {item["name"]: item["has_my_lantern"] for item in response.json()["data"]["booths"]}

    assert flags["멋사 주점"] is True
    assert flags["멋사"] is False


@pytest.mark.django_db
def test_search_includes_restroom_type(client):
    Booth.objects.create(
        name="명진관 1층 화장실",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
        restroom_type=Booth.RestroomType.FEMALE,
    )

    response = client.get(
        "/api/booths/search/",
        {"keyword": "명진관"},
    )

    assert response.status_code == 200

    items = response.json()["data"]["booths"]
    assert len(items) == 1
    assert items[0]["restroom_type"] == "FEMALE"
