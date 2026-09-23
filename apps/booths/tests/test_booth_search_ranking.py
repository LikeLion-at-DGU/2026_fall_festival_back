"""Booth search and ranking API tests."""

from datetime import date, time

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.booths.models import Booth, BoothMenu, BoothOperation
from apps.lanterns.models import Lantern

DATE_1 = date(2026, 9, 29)


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
    BoothMenu.objects.create(booth=by_menu, name="멋사라면", price=5000, sort_order=1)
    BoothMenu.objects.create(booth=by_menu, name="멋사김밥", price=3000, sort_order=2)
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
    response = client.get("/api/booths/search/", {"keyword": "멋사"})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "BOOTH_SEARCH_SUCCESS"
    names = [item["name"] for item in body["data"]["booths"]]
    # 정확 일치 → 이름 부분 일치 → 그 외(소개/메뉴 매칭, 이름 ㄱㄴㄷ순)
    assert names == ["멋사", "멋사 주점", "가나다 부스", "라면 부스"]
    assert body["data"]["total_count"] == 4
    assert body["data"]["booths"][0]["has_my_lantern"] is False
    partial_item = next(item for item in body["data"]["booths"] if item["name"] == "멋사 주점")
    assert partial_item["booth_size"] == "BIG"


@pytest.mark.django_db
def test_search_matches_menu_without_duplicates(client, search_booths):
    response = client.get("/api/booths/search/", {"keyword": "멋사라면"})
    names = [item["name"] for item in response.json()["data"]["booths"]]
    assert names == ["라면 부스"]


@pytest.mark.django_db
def test_search_filters_by_operating_date(client, search_booths):
    response = client.get(
        "/api/booths/search/",
        {"keyword": "멋사", "date": "2026-09-29", "time_slot": "NIGHT"},
    )
    names = [item["name"] for item in response.json()["data"]["booths"]]
    assert names == ["멋사 주점"]


@pytest.mark.django_db
def test_search_rejects_too_long_keyword(client, search_booths):
    response = client.get("/api/booths/search/", {"keyword": "가" * 51})
    assert response.status_code == 400
    assert response.json()["errors"]["keyword"] == "50자 이하로 입력해주세요."


@pytest.fixture
def ranking_booths(db):
    Booth.objects.create(
        name="가온 주점",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        lantern_count=32,
    )
    Booth.objects.create(
        name="나래 주점",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ALCOHOL,
        lantern_count=32,
    )
    Booth.objects.create(
        name="다솜 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        lantern_count=30,
    )
    # 시설은 랭킹·합계에서 제외되는지 검증용
    Booth.objects.create(
        name="명진관 화장실",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
        lantern_count=99,
    )


@pytest.mark.django_db
def test_ranking_ties_share_rank(client, ranking_booths):
    response = client.get("/api/booths/ranking/")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "BOOTH_RANKING_SUCCESS"
    ranking = body["data"]["ranking"]
    assert [(item["rank"], item["name"]) for item in ranking] == [
        (1, "가온 주점"),
        (1, "나래 주점"),
        (3, "다솜 부스"),
    ]
    # place_type=BOOTH만 합산 (시설 99개 제외)
    assert body["data"]["total_lantern_count"] == 94


@pytest.mark.django_db
def test_ranking_excludes_facilities(client, ranking_booths):
    response = client.get("/api/booths/ranking/")
    names = [item["name"] for item in response.json()["data"]["ranking"]]
    assert "명진관 화장실" not in names


@pytest.mark.django_db
def test_ranking_respects_limit(client, ranking_booths):
    response = client.get("/api/booths/ranking/", {"limit": "2"})
    assert len(response.json()["data"]["ranking"]) == 2


@pytest.mark.django_db
def test_ranking_rejects_invalid_limit(client, ranking_booths):
    for bad in ["0", "21", "abc"]:
        response = client.get("/api/booths/ranking/", {"limit": bad})
        assert response.status_code == 400
        assert response.json()["errors"]["limit"] == "1~20 사이의 정수로 입력해주세요."


@pytest.mark.django_db
def test_ranking_caches_query_between_requests(client, ranking_booths, django_assert_num_queries):
    first = client.get("/api/booths/ranking/")
    assert first.status_code == 200

    # 두 번째 요청은 booth_ranking()/total_lantern_count() 둘 다 캐시 히트라 DB 쿼리가 없어야 한다.
    with django_assert_num_queries(0):
        second = client.get("/api/booths/ranking/")
    assert second.status_code == 200
    assert second.json()["data"] == first.json()["data"]


@pytest.mark.django_db
def test_ranking_reflects_db_change_only_after_cache_cleared(client, ranking_booths):
    first = client.get("/api/booths/ranking/", {"limit": "1"})
    assert first.json()["data"]["ranking"][0]["name"] == "가온 주점"

    # 캐시가 살아있는 동안은 DB가 바뀌어도 랭킹에 반영되지 않는다 (TTL 동안의 지연).
    Booth.objects.filter(name="다솜 부스").update(lantern_count=999)
    stale = client.get("/api/booths/ranking/", {"limit": "1"})
    assert stale.json()["data"]["ranking"][0]["name"] == "가온 주점"

    # 캐시가 비워지면(TTL 만료를 흉내냄) 그제서야 최신 값이 반영된다.
    cache.clear()
    fresh = client.get("/api/booths/ranking/", {"limit": "1"})
    assert fresh.json()["data"]["ranking"][0]["name"] == "다솜 부스"


@pytest.mark.django_db
def test_search_rejects_time_slot_without_date(client, search_booths):
    response = client.get("/api/booths/search/", {"keyword": "멋사", "time_slot": "NIGHT"})
    assert response.status_code == 400
    assert response.json()["errors"]["time_slot"] == "time_slot은 date와 함께 사용해야 합니다."


@pytest.mark.django_db
def test_search_marks_my_lantern(auth_client, me, search_booths):
    Lantern.objects.create(
        user=me, booth=search_booths["partial"], message="화이팅", festival_date=DATE_1
    )
    response = auth_client.get("/api/booths/search/", {"keyword": "멋사"})
    flags = {item["name"]: item["has_my_lantern"] for item in response.json()["data"]["booths"]}
    assert flags["멋사 주점"] is True
    assert flags["멋사"] is False
