"""Booth model constraint tests."""

from datetime import date, time

import pytest
from django.db import IntegrityError

from apps.booths.models import Booth, BoothMenu, BoothOperation


@pytest.fixture
def booth(db):
    return Booth.objects.create(
        name="멋쟁이사자처럼 주점",
        subtitle="사회과학대학 광고홍보학과",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )


@pytest.mark.django_db
def test_booth_defaults(booth):
    assert booth.booth_size is None
    assert booth.lantern_count == 0
    assert booth.has_reusable_container is True
    assert booth.deleted_at is None


@pytest.mark.django_db
def test_booth_operation_slot_unique(booth):
    BoothOperation.objects.create(
        booth=booth,
        festival_date=date(2026, 9, 29),
        time_slot=BoothOperation.TimeSlot.NIGHT,
        open_at=time(17, 30),
        close_at=time(22, 0),
    )
    with pytest.raises(IntegrityError):
        BoothOperation.objects.create(
            booth=booth,
            festival_date=date(2026, 9, 29),
            time_slot=BoothOperation.TimeSlot.NIGHT,
            open_at=time(18, 0),
            close_at=time(21, 0),
        )


@pytest.mark.django_db
def test_booth_menu_ordering(booth):
    BoothMenu.objects.create(booth=booth, name="소주", price=4000, sort_order=2)
    BoothMenu.objects.create(booth=booth, name="제육볶음", price=12000, sort_order=1)
    names = list(booth.menus.values_list("name", flat=True))
    assert names == ["제육볶음", "소주"]


@pytest.mark.django_db
def test_booth_operation_placements_defaults_to_none(booth):
    operation = BoothOperation.objects.create(
        booth=booth,
        festival_date=date(2026, 9, 29),
        time_slot=BoothOperation.TimeSlot.NIGHT,
        open_at=time(17, 30),
        close_at=time(22, 0),
    )

    assert operation.placements is None
