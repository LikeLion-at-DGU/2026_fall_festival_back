"""seed_booths 커맨드 테스트 (레포에 커밋된 실제 booths.json·toilets.json 사용)."""

import json
from datetime import date, time
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.booths.management.commands.convert_booth_xlsx import _bool
from apps.booths.management.commands.seed_booths import DEFAULT_INPUT, DEFAULT_TOILETS_INPUT
from apps.booths.models import Booth, BoothMenu, BoothOperation

ROWS = [
    *json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))["booths"],
    *json.loads(DEFAULT_TOILETS_INPUT.read_text(encoding="utf-8"))["booths"],
]
BOOTH_COUNT = len(ROWS)
OPERATION_COUNT = sum(len(b["operations"]) for b in ROWS)
MENU_COUNT = sum(len(b["menus"]) for b in ROWS)


def _seed(*args):
    call_command("seed_booths", *args, stdout=StringIO())


@pytest.mark.django_db
def test_seed_booths_creates_all_rows():
    _seed()

    assert Booth.objects.count() == BOOTH_COUNT
    assert BoothOperation.objects.count() == OPERATION_COUNT
    assert BoothMenu.objects.count() == MENU_COUNT


@pytest.mark.django_db
def test_seed_booths_is_idempotent():
    _seed()
    _seed()

    assert Booth.objects.count() == BOOTH_COUNT
    assert BoothOperation.objects.count() == OPERATION_COUNT
    assert BoothMenu.objects.count() == MENU_COUNT


@pytest.mark.django_db
def test_seed_booths_updates_existing_booth_in_place():
    """이미 있는 부스는 같은 pk로 갱신해서, 달려 있는 등불이 지워지지 않게 한다."""
    existing = Booth.objects.create(
        name="경영학과",
        zone="혜화관",
        subtitle="예전 부스명",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        thumbnail_url="https://example.com/thumb.png",
    )
    BoothOperation.objects.create(
        booth=existing,
        festival_date=date(2026, 10, 1),
        time_slot=BoothOperation.TimeSlot.DAY,
        open_at=time(11, 0),
        close_at=time(16, 0),
    )

    _seed()

    existing.refresh_from_db()
    assert Booth.objects.count() == BOOTH_COUNT
    assert existing.subtitle == "강철상사 할로윈 파티"
    assert existing.category == Booth.Category.COLLAB
    # 엑셀에 없는 값은 유지
    assert existing.thumbnail_url == "https://example.com/thumb.png"
    # 파일에 없는 운영일정(10/1 주간)은 정리된다
    slots = list(existing.operations.values_list("festival_date", "time_slot"))
    assert slots == [(date(2026, 9, 29), "NIGHT")]


@pytest.mark.django_db
def test_seed_booths_keeps_booths_not_in_file():
    toilet = Booth.objects.create(
        name="혜화관 화장실",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
    )

    _seed()

    assert Booth.objects.filter(pk=toilet.pk).exists()


@pytest.mark.django_db
def test_seed_booths_stores_placements_and_menu_order():
    _seed()

    market = Booth.objects.get(name="플리마켓")
    placement = market.operations.first().placements[0]
    assert placement["structure"] == "MARKET"
    assert (placement["width"], placement["depth"]) == (21, 12)

    menus = Booth.objects.get(name="문과대학").menus.all()
    assert [m.sort_order for m in menus] == list(range(1, len(menus) + 1))
    assert menus[0].name == "오봉 모둠전"


@pytest.mark.django_db
def test_seed_booths_dry_run_does_not_write():
    _seed("--dry-run")

    assert Booth.objects.count() == 0


@pytest.mark.django_db
def test_seed_booths_food_truck_runs_every_slot():
    _seed()

    truck = Booth.objects.get(name="푸드트럭")
    assert truck.zone == "만해광장"
    assert truck.booth_size is None
    operations = truck.operations.all()
    assert operations.count() == 6
    for operation in operations:
        assert len(operation.placements) == 6
        assert {p["structure"] for p in operation.placements} == {"TRUCK"}


@pytest.mark.django_db
def test_seed_booths_only_liquor_facility_is_alcohol():
    """'주류' 칩은 주류 판매 시설만, 주·야간 부스(주점 포함)는 '부스' 칩(COLLAB·ETC)에 모인다."""
    _seed()

    alcohol = Booth.objects.filter(category=Booth.Category.ALCOHOL)
    assert list(alcohol.values_list("name", "place_type")) == [("주류 판매 부스", "FACILITY")]
    assert Booth.objects.get(name="문과대학").category == Booth.Category.ETC
    assert Booth.objects.get(name="경영학과").category == Booth.Category.COLLAB


@pytest.mark.django_db
def test_seed_booths_adds_toilets_without_position(client):
    """화장실은 층 단위 49곳이 좌표 없이 들어가고, 목록 API는 좌표를 null로 내려준다."""
    _seed()
    _seed()

    toilets = Booth.objects.filter(category=Booth.Category.TOILET)
    assert toilets.count() == 49
    assert not toilets.exclude(map_x__isnull=True).exists()
    # 구역이 빈 화장실도 재실행 시 중복되지 않는다.
    assert toilets.filter(zone__isnull=True).count() == 23

    response = client.get(
        "/api/booths/", {"date": "2026-09-29", "time_slot": "DAY", "category": "TOILET"}
    )
    booths = response.json()["data"]["booths"]
    assert len(booths) == 49
    assert {(b["map_x"], b["map_y"], tuple(b["placements"])) for b in booths} == {(None, None, ())}


@pytest.mark.django_db
def test_seed_booths_distinguishes_reusable_container_booths():
    _seed()

    hyehwa = Booth.objects.get(
        name="다회용기 부스 (혜화관)",
        zone="혜화관",
    )
    paljeongdo = Booth.objects.get(
        name="다회용기 부스 (팔정도)",
        zone="팔정도",
    )

    assert hyehwa.pk != paljeongdo.pk
    assert hyehwa.category == Booth.Category.COLLAB
    assert paljeongdo.category == Booth.Category.COLLAB


@pytest.mark.django_db
def test_seed_booths_collab_categories():
    _seed()

    collab = set(
        Booth.objects.filter(category=Booth.Category.COLLAB).values_list("name", flat=True)
    )
    assert collab == {
        "경영학과",
        "의료인공지능학과",
        "동국 108리더스",
        "축기단",
        "다회용기 부스 (혜화관)",
        "다회용기 부스 (팔정도)",
    }
    assert Booth.objects.get(name="애드러쉬").category == Booth.Category.ETC
    assert Booth.objects.get(name="오뚜기 진라면 서포터즈 진앤지니").category == Booth.Category.ETC


@pytest.mark.django_db
def test_eco_chip_still_shows_reusable_container_booths(client):
    """다회용기 부스는 COLLAB이지만 '동빛에코' 칩에도 나와야 한다."""
    _seed()

    response = client.get(
        "/api/booths/", {"date": "2026-09-30", "time_slot": "NIGHT", "category": "ECO"}
    )
    names = {b["name"] for b in response.json()["data"]["booths"]}
    assert names == {"다회용기 부스 (혜화관)", "다회용기 부스 (팔정도)"}


@pytest.mark.django_db
def test_seed_booths_restroom_type_and_reusable_container():
    _seed()

    toilets = Booth.objects.filter(category=Booth.Category.TOILET)
    assert toilets.filter(restroom_type=Booth.RestroomType.BOTH).count() == 42
    assert toilets.filter(restroom_type=Booth.RestroomType.MALE).count() == 4
    assert toilets.filter(restroom_type=Booth.RestroomType.FEMALE).count() == 3
    assert (
        not Booth.objects.exclude(category=Booth.Category.TOILET)
        .exclude(restroom_type__isnull=True)
        .exists()
    )
    # 엑셀 v10: 화장실을 뺀 장소 중 다회용기 미사용 21곳만 False
    non_toilets = Booth.objects.exclude(category=Booth.Category.TOILET)
    assert non_toilets.filter(has_reusable_container=False).count() == 21
    assert Booth.objects.get(name="문과대학").has_reusable_container is True


@pytest.mark.parametrize(
    ("value", "formula", "expected"),
    [(True, None, True), (None, "=TRUE()", True), (None, "=FALSE()", False), (None, "TRUE", True)],
)
def test_convert_reads_formula_booleans(value, formula, expected):
    assert _bool(value, formula, "N01") is expected


def test_convert_rejects_blank_booleans():
    with pytest.raises(CommandError):
        _bool(None, None, "N01")


@pytest.mark.django_db
def test_booth_chip_excludes_reusable_container_booths(client):
    """다회용기 부스는 '부스' 칩에서는 빠지고 '동빛에코' 칩에만 나온다."""
    _seed()

    response = client.get(
        "/api/booths/", {"date": "2026-09-30", "time_slot": "NIGHT", "category": "BOOTH"}
    )
    booths = response.json()["data"]["booths"]
    names = {b["name"] for b in booths}
    assert "다회용기 부스 (혜화관)" not in names
    assert "다회용기 부스 (팔정도)" not in names

    # 다른 협업 부스는 그대로 '부스' 칩에 남는다.
    response = client.get(
        "/api/booths/", {"date": "2026-09-29", "time_slot": "DAY", "category": "BOOTH"}
    )
    day_names = {b["name"] for b in response.json()["data"]["booths"]}
    assert {"축기단", "동국 108리더스"} <= day_names


@pytest.mark.django_db
def test_seed_booths_entrance_fee_and_menu_fixes():
    _seed()

    assert Booth.objects.get(name="열린전공학부").entrance_fee == 4000
    law_menus = list(Booth.objects.get(name="법과대학").menus.values_list("name", flat=True))
    assert "스파르타불닭 (치즈불닭볶음면)" in law_menus
    assert "스파르타불닭 (치즈불닭볶음변)" not in law_menus


@pytest.mark.django_db
def test_seed_booths_retires_toilets_missing_from_file(client):
    """건물 단위였던 옛 화장실은 toilets.json에 없으므로 soft delete된다."""
    old = Booth.objects.create(
        name="혜화관 화장실",
        zone="혜화관",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
    )
    BoothOperation.objects.create(
        booth=old,
        festival_date=date(2026, 9, 29),
        time_slot=BoothOperation.TimeSlot.DAY,
        open_at=time(11, 0),
        close_at=time(16, 30),
    )

    _seed()

    old.refresh_from_db()
    assert old.deleted_at is not None
    response = client.get(
        "/api/booths/", {"date": "2026-09-29", "time_slot": "DAY", "category": "TOILET"}
    )
    names = {b["name"] for b in response.json()["data"]["booths"]}
    assert "혜화관 화장실" not in names
    assert "혜화관 화장실 1층" in names


@pytest.mark.django_db
def test_seed_booths_dry_run_keeps_old_toilets():
    old = Booth.objects.create(
        name="혜화관 화장실",
        zone="혜화관",
        place_type=Booth.PlaceType.FACILITY,
        category=Booth.Category.TOILET,
    )

    _seed("--dry-run")

    old.refresh_from_db()
    assert old.deleted_at is None
