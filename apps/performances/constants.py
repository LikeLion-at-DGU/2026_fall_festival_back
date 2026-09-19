"""공연 도메인 상수."""

from datetime import timedelta


# 공연 시작 전 미리보기 시간
UPCOMING_PREVIEW_WINDOW = timedelta(hours=1)

# 지금 공연 중 카드 최대 노출 개수
NOW_PLAYING_LIMIT = 3