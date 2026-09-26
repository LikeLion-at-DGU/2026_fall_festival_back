"""apps/booths/data/booths.json(convert_booth_xlsx 결과)을 DB에 반영한다.

부스는 (name, zone)으로 기존 행을 찾아 갱신하고, 없으면 새로 만든다.
등불(Lantern)이 Booth를 CASCADE로 물고 있어서 부스는 절대 지웠다 다시
만들지 않는다 — 지우면 그 부스에 달린 등불이 전부 날아간다.

부스에 딸린 운영일정·메뉴는 파일 내용으로 통째로 맞춘다(파일에 없는
날짜/메뉴는 삭제). 여러 번 실행해도 결과가 같다 (멱등).

파일에 없는 기존 부스(화장실 등)는 건드리지 않는다.
썸네일·이미지·가는 길·화장실 구분·등불 수는 엑셀에 없는 값이라 갱신하지 않는다.

    python manage.py seed_booths --dry-run   # 무엇이 바뀌는지만 확인
    python manage.py seed_booths
"""

import json
from datetime import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.booths.models import Booth, BoothMenu, BoothOperation

DEFAULT_INPUT = Path(__file__).resolve().parents[2] / "data" / "booths.json"

BOOTH_FIELDS = [
    "subtitle",
    "place_type",
    "category",
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
        parser.add_argument("--input", default=str(DEFAULT_INPUT), help="입력 JSON 경로")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 저장하지 않고 결과만 출력한다 (트랜잭션 롤백).",
        )

    def handle(self, *args, **options):
        path = Path(options["input"])
        if not path.exists():
            raise CommandError(f"입력 파일이 없습니다: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))

        try:
            with transaction.atomic():
                stats = self._apply(payload["booths"])
                if options["dry_run"]:
                    raise DryRunRollback
        except DryRunRollback:
            self.stdout.write(self.style.WARNING("[dry-run] 롤백했습니다. DB는 바뀌지 않았습니다."))

        self.stdout.write(
            self.style.SUCCESS(
                f"{payload.get('source', path.name)} 반영 — "
                f"부스 생성 {stats['created']} · 갱신 {stats['updated']} / "
                f"운영일정 {stats['operations']} · 메뉴 {stats['menus']}"
            )
        )

    def _apply(self, booth_rows):
        stats = {"created": 0, "updated": 0, "operations": 0, "menus": 0}

        for row in booth_rows:
            booth, created = self._upsert_booth(row)
            stats["created" if created else "updated"] += 1
            stats["operations"] += self._sync_operations(booth, row["operations"])
            stats["menus"] += self._sync_menus(booth, row["menus"])

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
