"""common.clock 가상 축제 시간 테스트."""

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.utils import timezone

from common.clock import festival_localdate, festival_now

KST = ZoneInfo("Asia/Seoul")
REAL_NOW = datetime(2026, 9, 25, 10, 0, tzinfo=KST)
OFFSET_TO_0930_20H = int((datetime(2026, 9, 30, 20, 0, tzinfo=KST) - REAL_NOW).total_seconds())


def _freeze_real_now():
    return patch("django.utils.timezone.now", return_value=REAL_NOW)


@override_settings(FESTIVAL_TIME_ENABLED=False, FESTIVAL_TIME_OFFSET_SECONDS=OFFSET_TO_0930_20H)
def test_disabled_returns_real_time_even_if_offset_set():
    with _freeze_real_now():
        assert festival_now() == REAL_NOW
        assert festival_localdate() == date(2026, 9, 25)


@override_settings(FESTIVAL_TIME_ENABLED=True, FESTIVAL_TIME_OFFSET_SECONDS=OFFSET_TO_0930_20H)
def test_enabled_applies_offset_in_seoul_time():
    with _freeze_real_now():
        now = festival_now()
        assert now == REAL_NOW + timedelta(seconds=OFFSET_TO_0930_20H)
        assert now.hour == 20
        assert festival_localdate() == date(2026, 9, 30)
        # 보안·기록용 시간은 그대로 실제 시간
        assert timezone.now() == REAL_NOW
