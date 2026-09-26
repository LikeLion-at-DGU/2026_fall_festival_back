"""9/30, 10/1 라인업을 통째로 반영한다.

동아리 공연은 전부 확정된 실제 셋리스트다. '연예인 N'과 백상응원단은
셋리스트 화면 자체가 없는 공연이라 has_setlist=False로 두고 곡도 안 넣는다.

팀명 + festival_date로 기존 Performance를 찾고, 없으면 새로 만든다
(get_or_create). 여러 번 실행해도 안전하다 (멱등).

라인업에서 빠진 팀(예: 이름이 '음생' → '음샘'으로 바로잡힌 경우)은 그 날짜에서
soft delete한다. 라인업 목록이 그 날짜 공연의 정답이다. 
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.performances.models import Performance, Song

KST = ZoneInfo("Asia/Seoul")

#동아리 정보 추가 
CLUB_INFO = {
    "피어리스던": {
        "affiliation": "중앙 락메탈밴드 동아리",
    },
    "AJAX": {
        "affiliation": "중앙 힙합 동아리",
    },
    "뭉게구름": {
        "affiliation": "중앙 창작음악밴드 동아리",
    },
    "백상응원단": {
        "affiliation": None,
    },
    "두둠칫": {
        "affiliation": "중앙 커버댄스 동아리",
    },
    "잼잼": {
        "affiliation": "중앙 뮤지컬 동아리",
    },
    "목멱성": {
        "affiliation": "중앙 음악콘텐츠 동아리",
    },
    "아리랑": {
        "affiliation": "중앙 밴드 동아리",
    },
    "ODC": {
        "affiliation": "중앙 스트릿댄스 동아리",
    },
    "음샘": {
        "affiliation": "중앙 밴드 동아리",
    },
    "렛츠무드": {
        "affiliation": "중앙 락밴드 동아리",
    },
}

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
    "백상응원단": [
        ("단장입장곡", None),
        ("Show", None),
        ("애정표현", None),
        ("힘내", None),
        ("Butterfly", None),
        ("지금 널 찾아가고 있어", None),
        ("건국대학교 OX-K 찬조", None),
        ("기억의 숲", None),
        ("좋지 아니한가", None),
        ("아코 퍼포먼스", None),
        ("날아올라", None),
        ("빛을 따라서", None),
        ("오리 날다", None),
        ("알케인 스턴트 찬조", None),
        ("질풍가도", None),
        ("붉은 노을", None),
        ("예술이야", None),
        ("그대에게", None),
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
    "아리랑": [
        ("왜, 왜, 왜", "SUMIN, slom"),
        ("어른아이", "거미"),
        ("Violet", "The Volunteers"),
        ("Electra", "검정치마"),
        ("Wanli万里 + Citizen Kane", "혁오"),
    ],
    # 댄스 동아리라 곡 대신 장르별 무대. [장르]를 제목에 남겨 둔다.
    "ODC": [
        ("[하우스] keep me satisfied + you are the universe", None),
        ("[브레이킹] Body to Body + Madmax", None),
        ("[걸스힙합] 1 thing", None),
        ("[힙합] Can I Kick it? + J Dilla Life + 쌔끈해", None),
        ("[팝핑] Dangerous + Nobody Freakin'", None),
        ("[락킹] Treasure", None),
    ],
    "음샘": [
        ("This Love", "Maroon5"),
        ("Last night on earth", "Green day"),
        ("끼부리지마", "위너"),
        ("오르트구름", "윤하"),
    ],
    "렛츠무드": [
        ("불꽃놀이", "공원"),
        ("이상비행", "한로로"),
        ("해초", "한로로"),
        ("Basket Case", "Green Day"),
        ("알루미늄", "브로큰 발렌타인"),
    ],
}

# (team_name, start_time, end_time, has_setlist)
LINEUP_2026_09_30 = [
    ("피어리스던", "15:30", "16:00", True),
    ("AJAX", "16:00", "16:30", True),
    ("뭉게구름", "16:30", "17:00", True),
    ("백상응원단", "17:00", "18:30", True),
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
    ("음샘", "17:30", "18:00", True),
    ("렛츠무드", "18:00", "18:30", True),
    ("연예인 5", "18:30", "19:00", False),
    ("연예인 6", "19:00", "20:05", False),
    ("연예인 7", "20:05", "20:35", False),
    ("연예인 8", "20:35", "21:55", False),
    # 원본 시트는 '21:55~10:25'인데 30분 공연이라 22:25의 오타로 본다.
    ("연예인 9", "21:55", "22:25", False),
]


def _to_dt(festival_date, hhmm):
    hour, minute = map(int, hhmm.split(":"))
    return datetime.combine(festival_date, datetime.min.time(), tzinfo=KST).replace(
        hour=hour, minute=minute
    )


class Command(BaseCommand):
    help = "9/30·10/1 라인업 전체를 반영한다 (실제 셋리스트)."

    @transaction.atomic
    def handle(self, *args, **options):
        for festival_date, lineup in (
            (date(2026, 9, 30), LINEUP_2026_09_30),
            (date(2026, 10, 1), LINEUP_2026_10_01),
        ):
            for team_name, start_hhmm, end_hhmm, has_setlist in lineup:
                club_info = CLUB_INFO.get(team_name, {})
                start_at = _to_dt(festival_date, start_hhmm)
                end_at = _to_dt(festival_date, end_hhmm)
                if end_at <= start_at:
                    end_at += timedelta(days=1)

                performance, created = Performance.objects.get_or_create(
                    team_name=team_name,
                    festival_date=festival_date,
                    defaults={
                        "affiliation": club_info.get("affiliation"),
                        "image_url": None,
                        "start_at": start_at,
                        "end_at": end_at,
                        "has_setlist": has_setlist,
                    },
                )
                if not created:
                    performance.affiliation = club_info.get("affiliation")
                    performance.start_at = start_at
                    performance.end_at = end_at
                    performance.has_setlist = has_setlist
                    performance.deleted_at = None
                    performance.save(
                        update_fields=["affiliation","start_at", "end_at", "has_setlist", "deleted_at"]
                    )

                Song.objects.filter(performance=performance).delete()
                if has_setlist:
                    songs = REAL_SETLISTS.get(team_name, [])
                    Song.objects.bulk_create(
                        Song(performance=performance, title=title, artist=artist, sort_order=idx)
                        for idx, (title, artist) in enumerate(songs, start=1)
                    )

                tag = f"{len(songs)}곡" if has_setlist else "셋리스트없음"
                self.stdout.write(
                    self.style.SUCCESS(f"[{festival_date}] '{team_name}' 반영 완료 ({tag})")
                )

            removed = (
                Performance.objects.alive()
                .filter(festival_date=festival_date)
                .exclude(team_name__in=[team_name for team_name, *_ in lineup])
            )
            for performance in removed:
                message = f"[{festival_date}] '{performance.team_name}' 라인업에서 제외"
                self.stdout.write(self.style.WARNING(message))
            removed.soft_delete()
