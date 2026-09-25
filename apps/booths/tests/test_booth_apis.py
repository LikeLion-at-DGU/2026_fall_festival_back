"""Booth list and detail API tests."""

from datetime import date, time

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.booths.models import Booth, BoothMenu, BoothOperation
from apps.lanterns.models import Lantern

DATE_1 = date(2026, 9, 29)

PLACEMENTS = [
    {
        "unit_no": 1,
        "map_x": 14.0,
        "map_y": 36.0,
        "map_elevation": 2.5,
        "rotation": 0.0,
        "booth_size": "BIG",
    },
    {
        "unit_no": 2,
        "map_x": 21.0,
        "map_y": 36.0,
        "map_elevation": 2.5,
        "rotation": 0.0,
        "booth_size": "BIG",
    },
]


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def booths(db):
    popular = Booth.objects.create(
        name="멋쟁이사자처럼 주점",
        subtitle="사회과학대학 광고홍보학과",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        booth_size=Booth.BoothSize.BIG,
        lantern_count=32,
    )
    normal = Booth.objects.create(
        name="가나다 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        booth_size=Booth.BoothSize.SMALL,
        lantern_count=5,
    )
    collab = Booth.objects.create(
        name="총학생회 협업 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.COLLAB,
        lantern_count=1,
    )
    alcohol = Booth.objects.create(
        name="건축공학과 주점",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ALCOHOL,
        lantern_count=0,
    )
    no_operation = Booth.objects.create(
        name="운영정보 없는 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )
    toilet = Booth.objects.create(
        name="명진관 화장실",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
        restroom_type=Booth.RestroomType.BOTH,
        directions="명진관 1층 동쪽 출입구에서 50m 직진",
    )
    for booth in [popular, normal, collab, alcohol, toilet]:
        BoothOperation.objects.create(
            booth=booth,
            festival_date=DATE_1,
            time_slot=BoothOperation.TimeSlot.NIGHT,
            open_at=time(17, 30),
            close_at=time(22, 0),
        )
    BoothMenu.objects.create(booth=popular, name="소주", price=4000, sort_order=2)
    BoothMenu.objects.create(booth=popular, name="제육볶음", price=12000, sort_order=1)
    return {
        "popular": popular,
        "normal": normal,
        "collab": collab,
        "alcohol": alcohol,
        "no_operation": no_operation,
        "toilet": toilet,
    }


@pytest.mark.django_db
def test_booth_list_returns_only_operating_booths(client, booths):
    response = client.get("/api/booths/", {"date": "2026-09-29", "time_slot": "NIGHT"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["code"] == "BOOTH_LIST_SUCCESS"
    names = [item["name"] for item in body["data"]["booths"]]
    assert "운영정보 없는 부스" not in names
    assert body["data"]["total_count"] == 5


@pytest.mark.django_db
def test_booth_list_orders_by_name(client, booths):
    # 전체 목록은 이름 ㄱㄴㄷ순 (등불 수와 무관)
    response = client.get("/api/booths/", {"date": "2026-09-29", "time_slot": "NIGHT"})
    items = response.json()["data"]["booths"]
    names = [item["name"] for item in items]
    assert names == [
        "가나다 부스",
        "건축공학과 주점",
        "멋쟁이사자처럼 주점",
        "명진관 화장실",
        "총학생회 협업 부스",
    ]
    first = items[0]
    assert first["has_my_lantern"] is False
    assert first["operation"] == {"open_at": "17:30", "close_at": "22:00"}

    sizes = {item["name"]: item["booth_size"] for item in items}
    assert sizes["가나다 부스"] == "SMALL"
    assert sizes["멋쟁이사자처럼 주점"] == "BIG"


@pytest.mark.django_db
def test_booth_chip_groups_collab_first_in_name_order(client, booths):
    # '부스' 칩: 협업 부스(ㄱㄴㄷ순) → 일반 부스(ㄱㄴㄷ순). 등불 수와 무관
    response = client.get(
        "/api/booths/", {"date": "2026-09-29", "time_slot": "NIGHT", "category": "BOOTH"}
    )
    names = [item["name"] for item in response.json()["data"]["booths"]]
    assert names == ["총학생회 협업 부스", "가나다 부스", "멋쟁이사자처럼 주점"]


@pytest.mark.django_db
def test_booth_list_filters_by_category(client, booths):
    response = client.get(
        "/api/booths/",
        {"date": "2026-09-29", "time_slot": "NIGHT", "category": "TOILET"},
    )
    items = response.json()["data"]["booths"]

    assert [item["name"] for item in items] == ["명진관 화장실"]
    assert items[0]["directions"] == "명진관 1층 동쪽 출입구에서 50m 직진"
    assert items[0]["booth_size"] is None
    assert items[0]["restroom_type"] == "BOTH"


@pytest.mark.django_db
def test_booth_list_defaults_to_first_day_outside_festival(client, booths):
    # 실행 시점이 축제 기간 밖이면 기본 날짜가 2026-09-29로 판정되는지
    response = client.get("/api/booths/", {"time_slot": "NIGHT"})
    assert response.status_code == 200
    assert response.json()["data"]["festival_date"] == "2026-09-29"


@pytest.mark.django_db
def test_booth_list_rejects_out_of_range_date(client, booths):
    response = client.get("/api/booths/", {"date": "2026-10-05"})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_FESTIVAL_DATE"


@pytest.mark.django_db
def test_booth_list_rejects_invalid_time_slot_and_category(client, booths):
    response = client.get("/api/booths/", {"time_slot": "MORNING"})
    assert response.status_code == 400
    assert response.json()["errors"]["time_slot"] == "DAY 또는 NIGHT 중에서 선택해주세요."

    # 삭제된 협업 칩 값(COLLAB)은 더 이상 유효하지 않다
    response = client.get("/api/booths/", {"category": "COLLAB"})
    assert response.status_code == 400
    assert (
        response.json()["errors"]["category"]
        == "BOOTH / TOILET / ALCOHOL / ECO 중에서 선택해주세요."
    )


@pytest.mark.django_db
def test_booth_detail_includes_operations_and_menus(client, booths):
    booth = booths["popular"]
    response = client.get(f"/api/booths/{booth.id}/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["booth_id"] == booth.id
    assert data["has_my_lantern"] is False
    assert len(data["operations"]) == 1
    assert [menu["name"] for menu in data["menus"]] == ["제육볶음", "소주"]
    assert data["booth_size"] == "BIG"


@pytest.mark.django_db
def test_booth_detail_returns_404_for_missing_booth(client, booths):
    response = client.get("/api/booths/999999/")
    assert response.status_code == 404
    assert response.json()["code"] == "BOOTH_NOT_FOUND"


@pytest.mark.django_db
def test_public_booth_reads_ignore_stale_access_token(client, booths):
    # 공개 조회의 선택 인증은 브라우저에 남은 만료·폐기 토큰 때문에 전체 요청을 막지 않는다.
    client.credentials(HTTP_AUTHORIZATION="Bearer stale-access-token")
    requests = [
        ("/api/booths/", {"date": "2026-09-29", "time_slot": "NIGHT"}),
        (f"/api/booths/{booths['popular'].id}/", {}),
        ("/api/booths/search/", {"keyword": "멋쟁이사자처럼"}),
    ]

    for url, params in requests:
        response = client.get(url, params)
        assert response.status_code == 200
        assert response.json()["success"] is True

    list_item = client.get("/api/booths/", {"date": "2026-09-29", "time_slot": "NIGHT"}).json()[
        "data"
    ]["booths"][0]
    assert list_item["has_my_lantern"] is False


@pytest.mark.django_db
def test_booth_list_marks_booths_with_my_lantern(auth_client, me, booths):
    Lantern.objects.create(user=me, booth=booths["popular"], message="화이팅", festival_date=DATE_1)
    # 삭제한 등불은 표시하지 않는다
    Lantern.objects.create(
        user=me,
        booth=booths["normal"],
        message="지운 등불",
        festival_date=DATE_1,
        deleted_at=timezone.now(),
        deleted_by=Lantern.DeletedBy.USER,
    )
    response = auth_client.get("/api/booths/", {"date": "2026-09-29", "time_slot": "NIGHT"})
    flags = {item["name"]: item["has_my_lantern"] for item in response.json()["data"]["booths"]}
    assert flags["멋쟁이사자처럼 주점"] is True
    assert flags["가나다 부스"] is False
    assert flags["건축공학과 주점"] is False


@pytest.mark.django_db
def test_booth_detail_marks_my_lantern(auth_client, me, booths):
    booth = booths["popular"]
    Lantern.objects.create(user=me, booth=booth, message="화이팅", festival_date=DATE_1)
    response = auth_client.get(f"/api/booths/{booth.id}/")
    assert response.json()["data"]["has_my_lantern"] is True


@pytest.mark.django_db
def test_booth_list_returns_all_placements(client, booths):
    operation = BoothOperation.objects.get(
        booth=booths["popular"],
        festival_date=DATE_1,
        time_slot=BoothOperation.TimeSlot.NIGHT,
    )
    operation.placements = PLACEMENTS
    operation.save(update_fields=["placements"])

    response = client.get(
        "/api/booths/",
        {"date": "2026-09-29", "time_slot": "NIGHT"},
    )

    assert response.status_code == 200

    items = response.json()["data"]["booths"]
    popular = next(item for item in items if item["name"] == "멋쟁이사자처럼 주점")

    assert popular["placements"] == PLACEMENTS
    assert len(popular["placements"]) == 2


@pytest.mark.django_db
def test_booth_list_returns_empty_placements_when_not_registered(client, booths):
    response = client.get(
        "/api/booths/",
        {"date": "2026-09-29", "time_slot": "NIGHT"},
    )

    items = response.json()["data"]["booths"]
    normal = next(item for item in items if item["name"] == "가나다 부스")

    assert normal["placements"] == []


@pytest.mark.django_db
def test_booth_detail_includes_operation_placements(client, booths):
    operation = BoothOperation.objects.get(
        booth=booths["popular"],
        festival_date=DATE_1,
        time_slot=BoothOperation.TimeSlot.NIGHT,
    )
    operation.placements = PLACEMENTS
    operation.save(update_fields=["placements"])

    response = client.get(f"/api/booths/{booths['popular'].id}/")

    assert response.status_code == 200

    operations = response.json()["data"]["operations"]
    assert operations[0]["placements"] == PLACEMENTS


@pytest.mark.django_db
def test_booth_detail_includes_restroom_type(client, booths):
    toilet = booths["toilet"]

    response = client.get(f"/api/booths/{toilet.id}/")

    assert response.status_code == 200
    assert response.json()["data"]["restroom_type"] == "BOTH"
