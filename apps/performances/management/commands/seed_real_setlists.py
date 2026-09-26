"""9/30, 10/1 라인업을 통째로 반영한다.

피어리스던·AJAX·뭉게구름·두둠칫·목멱성·잼잼은 확정된 실제 셋리스트, 나머지는 아직 셋리스트가
안 나와서 목업 곡으로 채운다 (제목에 "목업곡"이 들어가서 실수로 실제인
척 쓰이지 않게 표시). '연예인 N'과 백상응원단은 셋리스트 화면 자체가
없는 공연이라 has_setlist=False로 두고 곡도 안 넣는다.

쟁쟁(10/1)은 원본 시트 이미지 글자가 뭉개져서 정확히 못 읽어 목업으로
채웠다. 실제 셋리스트가 확정되면 REAL_SETLISTS에 추가해서 재실행하면 된다.

팀명 + festival_date로 기존 Performance를 찾고, 없으면 새로 만든다
(get_or_create). 여러 번 실행해도 안전하다 (멱등).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.performances.models import Performance, Song

KST = ZoneInfo("Asia/Seoul")

# 확정된 실제 셋리스트. (title, artist) — artist가 None이면 팀 자작곡.
REAL_SETLISTS = {
    "피어리스던": [
        ("My Hero", "Foo Fighters"),
        ("룩셈부르크", "크라잉넛"),
        ("Baby Baby", "銀杏BOYZ"),
        ("Skool Kill", "銀杏BOYZ"),
        ("한 겨울밤의 꿈", "초록불꽃소년단"),
    ],
    "AJAX": [
        ("Money back", None),
        ("복권", None),
        ("Pop it up", None),
        ("Shine", None),
        ("빨리", None),
        ("Wait 4 me", None),
        ("BAD 놀이", None),
        ("차광배", None),
        ("AJAX", None),
    ],
    "뭉게구름": [
        ("비행소녀", "김마리"),
        ("괴물", "YOASOBI"),
        ("ダンス・デカダンス", "Chevon"),
        ("아윌다이포유❤️x3", "잔나비"),
        ("너와 나", "한로로"),
    ],
    "두둠칫": [
        ("걸스네버다이", "트리플에스"),
        ("러브어택", "리센느"),
        ("WDA", "에스파"),
        ("레드레드", "코르티스"),
        ("레몬탱", "하츠투하츠"),
        ("cheer up", "트와이스"),
        ("do your dance", "라이즈"),
        ("아마겟돈", "에스파"),
    ],
    "목멱성": [
        ("너와나", "한로로"),
        ("Pain", "하현상"),
        ("항해", "유다빈밴드"),
        ("불", "유다빈밴드"),
        ("뜨거운안녕", "싸이(Feat. 성시경)"),
    
    ],
    "잼잼": [
        ("Seasons of love", "뮤지컬 렌트"),
        ("사랑은 마치", "뮤지컬 레드북"),
        ("끼리끼리", "뮤지컬 난쟁이들"),
        ("steal your rock n roll", "뮤지컬 멤피스"),
        ("Land of Lola", "뮤지컬 킹키부츠"),
        ("Raise you up", "뮤지컬 킹키부츠"),
    ],
}

# (team_name, start_time, end_time, has_setlist)
LINEUP_2026_09_30 = [
    ("피어리스던", "15:30", "16:00", True),
    ("AJAX", "16:00", "16:30", True),
    ("뭉게구름", "16:30", "17:00", True),
    ("백상응원단", "17:00", "18:30", False),
    ("연예인 1", "18:30", "19:05", False),
    ("두둠칫", "19:05", "19:35", True),
    ("연예인 2", "19:35", "20:20", False),
    ("연예인 3", "20:20", "20:55", False),
    ("연예인 4", "20:55", "21:30", False),
]

LINEUP_2026_10_01 = [
    ("잼잼", "15:30", "16:00", True),
    ("목멱성", "16:00", "16:30", True),
    ("아리랑", "16:30", "17:00", True),
    ("ODC", "17:00", "17:30", True),
    ("음생", "17:30", "18:00", True),
    ("렛츠무드", "18:00", "18:30", True),
    ("연예인 5", "18:30", "19:35", False),
    ("연예인 6", "19:35", "20:05", False),
    ("연예인 7", "20:05", "21:00", False),
    ("연예인 8", "21:00", "21:35", False),
]


def _mock_songs(team_name, count=2):
    return [(f"{team_name} 목업곡 {i}", "목업 아티스트") for i in range(1, count + 1)]


def _to_dt(festival_date, hhmm):
    hour, minute = map(int, hhmm.split(":"))
    return datetime.combine(festival_date, datetime.min.time(), tzinfo=KST).replace(
        hour=hour, minute=minute
    )


class Command(BaseCommand):
    help = "9/30·10/1 라인업 전체를 반영한다 (확정 팀 실제 셋리스트 + 나머지 목업)."

    @transaction.atomic
    def handle(self, *args, **options):
        for festival_date, lineup in (
            (date(2026, 9, 30), LINEUP_2026_09_30),
            (date(2026, 10, 1), LINEUP_2026_10_01),
        ):
            for team_name, start_hhmm, end_hhmm, has_setlist in lineup:
                start_at = _to_dt(festival_date, start_hhmm)
                end_at = _to_dt(festival_date, end_hhmm)
                if end_at <= start_at:
                    end_at += timedelta(days=1)

                performance, created = Performance.objects.get_or_create(
                    team_name=team_name,
                    festival_date=festival_date,
                    defaults={
                        "description": "(목업 데이터)",
                        "start_at": start_at,
                        "end_at": end_at,
                        "has_setlist": has_setlist,
                    },
                )
                if not created:
                    performance.start_at = start_at
                    performance.end_at = end_at
                    performance.has_setlist = has_setlist
                    performance.save(update_fields=["start_at", "end_at", "has_setlist"])

                Song.objects.filter(performance=performance).delete()
                if has_setlist:
                    songs = REAL_SETLISTS.get(team_name) or _mock_songs(team_name)
                    Song.objects.bulk_create(
                        Song(performance=performance, title=title, artist=artist, sort_order=idx)
                        for idx, (title, artist) in enumerate(songs, start=1)
                    )

                tag = "실제" if team_name in REAL_SETLISTS else ("목업" if has_setlist else "셋리스트없음")
                self.stdout.write(
                    self.style.SUCCESS(f"[{festival_date}] '{team_name}' 반영 완료 ({tag})")
                )