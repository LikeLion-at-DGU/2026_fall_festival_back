"""공연 도메인 판정 로직."""

from django.conf import settings

from .constants import NOW_PLAYING_LIMIT, UPCOMING_PREVIEW_WINDOW
from .selectors import list_live, list_upcoming_on


def is_live(performance, now):
    """현재 공연 진행 여부를 반환한다."""
    return performance.start_at <= now <= performance.end_at


def resolve_festival_date(requested_date, today):
    """타임테이블 조회에 사용할 날짜를 결정한다."""
    if requested_date is not None:
        return requested_date

    if settings.FESTIVAL_START_DATE <= today <= settings.FESTIVAL_END_DATE:
        return today

    return settings.FESTIVAL_START_DATE


def now_playing_performances(now, limit=NOW_PLAYING_LIMIT):
    """홈 화면에 노출할 현재 및 예정 공연을 결정한다."""
    live = list_live(now)

    if live:
        # 자정을 넘긴 공연은 해당 공연의 축제 날짜를 기준으로 조회
        festival_date = live[0].festival_date
        upcoming = list_upcoming_on(festival_date, now, limit - len(live))
        return (live + upcoming)[:limit]

    festival_date = resolve_festival_date(None, now.date())
    upcoming = list_upcoming_on(festival_date, now, limit)

    if not upcoming:
        return []

    # 첫 공연이 1시간 이내에 시작하는 경우에만 미리보기 노출
    if upcoming[0].start_at - now <= UPCOMING_PREVIEW_WINDOW:
        return upcoming

    return []