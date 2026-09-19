"""프론트 연동 및 QA용 공연 목업 데이터 생성 커맨드."""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.performances.models import Performance, Song


DAY_1_LINEUP = [
    (
        "음샘",
        "밴드동아리",
        time(16, 0),
        60,
        [
            ("The Volunteer", "S.A.D"),
            ("Heroine", "back number"),
            ("kimi wa Rock Wo Kikanai", "aimyon"),
        ],
    ),
    (
        "소리터",
        "풍물패",
        time(17, 30),
        45,
        [
            ("사물놀이 판굿", None),
        ],
    ),
    (
        "초대가수 A",
        None,
        time(19, 0),
        60,
        [],
    ),
]

DAY_2_LINEUP = [
    (
        "댄스동아리 하이킥",
        "중앙동아리",
        time(16, 30),
        40,
        [
            ("Magnetic", "ILLIT"),
            ("Supernova", "aespa"),
        ],
    ),
    (
        "어쿠스틱 소모임",
        "음악동아리",
        time(18, 0),
        50,
        [
            ("밤편지", "아이유"),
            ("모든 날, 모든 순간", "폴킴"),
        ],
    ),
]

DAY_3_LINEUP = [
    (
        "졸업생 밴드",
        "동문",
        time(17, 0),
        50,
        [
            ("청춘", "산울림"),
        ],
    ),
    (
        "초대가수 B",
        None,
        time(19, 30),
        70,
        [],
    ),
]


LINEUPS = [
    DAY_1_LINEUP,
    DAY_2_LINEUP,
    DAY_3_LINEUP,
]


class Command(BaseCommand):
    help = "개발용 공연 및 셋리스트 목업 데이터를 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="기존 공연 데이터를 삭제하고 목업 데이터를 다시 생성합니다.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # 운영 환경에서 실수로 목업 데이터를 생성하지 못하도록 제한
        if not settings.DEBUG:
            raise CommandError(
                "공연 목업 데이터는 개발 환경에서만 생성할 수 있습니다."
            )

        has_existing_data = Performance.objects.exists()

        if has_existing_data and not options["reset"]:
            raise CommandError(
                "기존 공연 데이터가 존재합니다. "
                "초기화 후 다시 생성하려면 --reset 옵션을 사용해주세요."
            )

        if options["reset"]:
            # 개발용 목업 데이터를 완전히 초기화
            deleted, _ = Performance.objects.all().delete()
            self.stdout.write(
                f"기존 공연 관련 데이터 {deleted}건 삭제"
            )

        festival_dates = self._festival_dates()
        created_count = 0

        for festival_date, lineup in zip(
            festival_dates,
            LINEUPS,
            strict=False,
        ):
            for (
                team_name,
                affiliation,
                start_time,
                duration,
                songs,
            ) in lineup:
                start_at = timezone.make_aware(
                    datetime.combine(
                        festival_date,
                        start_time,
                    )
                )

                performance = Performance.objects.create(
                    team_name=team_name,
                    affiliation=affiliation,
                    description=f"{team_name} 공연입니다. (목업 데이터)",
                    festival_date=festival_date,
                    start_at=start_at,
                    end_at=start_at + timedelta(minutes=duration),
                )

                Song.objects.bulk_create(
                    [
                        Song(
                            performance=performance,
                            title=title,
                            artist=artist,
                            sort_order=index,
                        )
                        for index, (title, artist) in enumerate(
                            songs,
                            start=1,
                        )
                    ]
                )

                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"공연 목업 데이터 {created_count}건 생성 완료"
            )
        )

    def _festival_dates(self):
        """축제 기간의 날짜 목록을 반환한다."""

        dates = []
        current = settings.FESTIVAL_START_DATE

        while current <= settings.FESTIVAL_END_DATE:
            dates.append(current)
            current += timedelta(days=1)

        return dates