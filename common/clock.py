"""축제 비즈니스 시간.

EC2 시스템 시간은 절대 바꾸지 않고, 축제 당일 기능을 미리 테스트할 때만
FESTIVAL_TIME_ENABLED / FESTIVAL_TIME_OFFSET_SECONDS로 가상 시간을 적용한다.

이 모듈은 공연 LIVE, 부스 DAY/NIGHT, 등불·쿠폰 날짜 판정에만 사용한다.
JWT, Refresh Token, created_at/updated_at/deleted_at, R2 업로드 등
보안·기록용 시간은 반드시 django.utils.timezone을 직접 사용한다.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def is_festival_time_enabled():
    return settings.FESTIVAL_TIME_ENABLED


def festival_now():
    """축제 비즈니스 기준 현재 시각(Asia/Seoul)."""
    if not is_festival_time_enabled():
        return timezone.localtime()
    offset = timedelta(seconds=settings.FESTIVAL_TIME_OFFSET_SECONDS)
    return timezone.localtime(timezone.now() + offset)


def festival_localdate():
    """축제 비즈니스 기준 오늘 날짜(Asia/Seoul)."""
    if not is_festival_time_enabled():
        return timezone.localdate()
    return festival_now().date()
