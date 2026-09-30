"""부스·화장실 데이터를 DB에 반영한다.

- apps/booths/data/booths.json: 부스·시설 (convert_booth_xlsx 결과)
- apps/booths/data/toilets.json: 화장실 층 단위 목록 (직접 관리, 엑셀과 별개)

부스는 (name, zone)으로 기존 행을 찾아 갱신하고, 없으면 새로 만든다.
등불(Lantern)이 Booth를 CASCADE로 물고 있어서 부스는 절대 지웠다 다시
만들지 않는다 — 지우면 그 부스에 달린 등불이 전부 날아간다.

부스에 딸린 운영일정·메뉴는 파일 내용으로 통째로 맞춘다(파일에 없는
날짜/메뉴는 삭제). 여러 번 실행해도 결과가 같다 (멱등).

파일에 없는 기존 부스는 건드리지 않는다. 단 화장실은 toilets.json이 전체 목록이라
거기에 없는 화장실은 soft delete한다 (건물 단위 → 층 단위로 바꿀 때 옛 행 정리).
화장실에는 등불을 달 수 없어서 soft delete해도 등불이 사라지지 않는다.
썸네일·이미지·가는 길·등불 수는 엑셀에 없는 값이라 갱신하지 않는다.

    python manage.py seed_booths --dry-run   # 무엇이 바뀌는지만 확인
    python manage.py seed_booths
"""

import json
from datetime import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.booths.models import Booth, BoothMenu, BoothOperation

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_INPUT = DATA_DIR / "booths.json"
DEFAULT_TOILETS_INPUT = DATA_DIR / "toilets.json"

BOOTH_FIELDS = [
    "subtitle",
    "place_type",
    "category",
    "restroom_type",
    "booth_size",
    "location_detail",
    "map_x",
    "map_y",
    "map_elevation",
    "rotation",
    "description",
    "event_description",
    "instagram_id",
    "entrance_fee",
    "has_reusable_container",
]


class DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = "부스·운영일정·메뉴 데이터(booths.json)를 DB에 반영한다."

    def add_arguments(self, parser):
        parser.add_argument("--input", default=str(DEFAULT_INPUT), help="부스 JSON 경로")
        parser.add_argument(
            "--toilets", default=str(DEFAULT_TOILETS_INPUT), help="화장실 JSON 경로"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 저장하지 않고 결과만 출력한다 (트랜잭션 롤백).",
        )

    def handle(self, *args, **options):
        payload = self._load(options["input"])
        toilets = self._load(options["toilets"])

        booth_rows = payload["booths"]
        toilet_rows = toilets["booths"]
        if any(row["category"] != Booth.Category.TOILET for row in toilet_rows):
            raise CommandError("화장실 JSON에 화장실이 아닌 항목이 있습니다.")
        if any(row["category"] == Booth.Category.TOILET for row in booth_rows):
            raise CommandError(
                "부스 JSON에 화장실이 있습니다. 화장실은 toilets.json에서 관리합니다."
            )

        try:
            with transaction.atomic():
                stats = self._apply(booth_rows + toilet_rows)
                if options["dry_run"]:
                    raise DryRunRollback
        except DryRunRollback:
            self.stdout.write(self.style.WARNING("[dry-run] 롤백했습니다. DB는 바뀌지 않았습니다."))

        self.stdout.write(
            self.style.SUCCESS(
                f"{payload.get('source', 'booths.json')} + {toilets.get('source', 'toilets.json')}"
                f" 반영 — 부스 생성 {stats['created']} · 갱신 {stats['updated']} / "
                f"운영일정 {stats['operations']} · 메뉴 {stats['menus']} / "
                f"목록에서 빠진 화장실 정리 {stats['retired_toilets']}"
            )
        )

    def _load(self, path):
        path = Path(path)
        if not path.exists():
            raise CommandError(f"입력 파일이 없습니다: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _apply(self, booth_rows):
        stats = {"created": 0, "updated": 0, "operations": 0, "menus": 0}

        seen_keys = set()
        for row in booth_rows:
            if (row["name"], row["zone"]) in seen_keys:
                raise CommandError(f"'{row['name']}'({row['zone']})이 파일에 두 번 있습니다.")
            seen_keys.add((row["name"], row["zone"]))

        kept_ids = []
        for row in booth_rows:
            booth, created = self._upsert_booth(row)
            kept_ids.append(booth.id)
            stats["created" if created else "updated"] += 1
            stats["operations"] += self._sync_operations(booth, row["operations"])
            stats["menus"] += self._sync_menus(booth, row["menus"])

        stats["retired_toilets"] = (
            Booth.objects.filter(category=Booth.Category.TOILET, deleted_at__isnull=True)
            .exclude(id__in=kept_ids)
            .update(deleted_at=timezone.now())
        )
        return stats

    def _upsert_booth(self, row):
        matches = list(
            Booth.objects.filter(name=row["name"], zone=row["zone"], deleted_at__isnull=True)
        )
        if len(matches) > 1:
            raise CommandError(
                f"[{row['key']}] '{row['name']}'({row['zone']}) 부스가 DB에 "
                f"{len(matches)}개 있습니다. 중복을 먼저 정리해주세요."
            )

        values = {field: row[field] for field in BOOTH_FIELDS}
        if matches:
            booth = matches[0]
            for field, value in values.items():
                setattr(booth, field, value)
            booth.save(update_fields=[*BOOTH_FIELDS, "updated_at"])
            return booth, False

        booth = Booth.objects.create(name=row["name"], zone=row["zone"], **values)
        return booth, True

    def _sync_operations(self, booth, operation_rows):
        keep_ids = []
        for row in operation_rows:
            operation, _ = BoothOperation.objects.update_or_create(
                booth=booth,
                festival_date=row["festival_date"],
                time_slot=row["time_slot"],
                defaults={
                    "open_at": time.fromisoformat(row["open_at"]),
                    "close_at": time.fromisoformat(row["close_at"]),
                    "placements": row["placements"] or None,
                    "deleted_at": None,
                },
            )
            keep_ids.append(operation.id)

        BoothOperation.objects.filter(booth=booth).exclude(id__in=keep_ids).delete()
        return len(keep_ids)

    def _sync_menus(self, booth, menu_rows):
        BoothMenu.objects.filter(booth=booth).delete()
        BoothMenu.objects.bulk_create(
            BoothMenu(booth=booth, name=row["name"], price=row["price"], sort_order=index)
            for index, row in enumerate(menu_rows, start=1)
        )
        return len(menu_rows)
