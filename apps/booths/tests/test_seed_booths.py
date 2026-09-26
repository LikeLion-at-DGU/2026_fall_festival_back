"""seed_booths 커맨드 테스트 (레포에 커밋된 실제 booths.json 사용)."""

import json
from datetime import date, time
from io import StringIO

import pytest
from django.core.management import call_command

from apps.booths.management.commands.seed_booths import DEFAULT_INPUT
from apps.booths.models import Booth, BoothMenu, BoothOperation

DATA = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))
BOOTH_COUNT = len(DATA["booths"])
OPERATION_COUNT = sum(len(b["operations"]) for b in DATA["booths"])
MENU_COUNT = sum(len(b["menus"]) for b in DATA["booths"])


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
        assert len(operation.placements) == 11
        assert {p["structure"] for p in operation.placements} == {"TRUCK"}
