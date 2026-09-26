"""부스 정리 엑셀(축제부스_전체정리_vN.xlsx)을 seed_booths용 JSON으로 변환한다.

엑셀은 대협·재원이 관리하는 원본이라 레포에 넣지 않고, 이 커맨드로 뽑은
JSON(apps/booths/data/booths.json)만 커밋한다. 서버는 JSON만 읽으므로
openpyxl은 이 커맨드를 돌리는 로컬에만 있으면 된다.

    pip install openpyxl
    python manage.py convert_booth_xlsx "축제부스_전체정리_v7.xlsx"

시트/열 구성이 바뀌면 HEADER_ROW와 각 시트의 열 이름만 맞춰주면 된다.
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "booths.json"

# 모든 데이터 시트는 1~3행이 제목/설명/빈 줄이고 4행이 헤더다.
HEADER_ROW = 4

# 구조물 열 예: "MARKET 21×12m" → placements에 structure/width/depth로 나간다.
STRUCTURE_PATTERN = re.compile(r"^(?P<kind>[A-Z]+)\s+(?P<width>[\d.]+)\s*[×x]\s*(?P<depth>[\d.]+)")


def _sheet_rows(workbook, sheet_name):
    """헤더 첫 줄(개행 앞)을 키로 한 dict 목록. 임시키/날짜가 비어 있는 줄은 건너뛴다."""
    rows = workbook[sheet_name].iter_rows(min_row=HEADER_ROW, values_only=True)
    header = [str(cell).split("\n")[0].strip() if cell else None for cell in next(rows)]
    for row in rows:
        if row[0] is None:
            continue
        yield dict(zip(header, row, strict=False))


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _number(value):
    if value is None:
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def _date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)


def _structure(value):
    value = _text(value)
    if not value:
        return {}
    match = STRUCTURE_PATTERN.match(value)
    if not match:
        raise CommandError(f"구조물 표기를 해석할 수 없습니다: {value!r}")
    return {
        "structure": match["kind"],
        "width": _number(match["width"]),
        "depth": _number(match["depth"]),
    }


class Command(BaseCommand):
    help = "부스 정리 엑셀을 seed_booths용 JSON으로 변환한다 (로컬 전용, openpyxl 필요)."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", help="축제부스_전체정리_vN.xlsx 경로")
        parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="출력 JSON 경로")

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError("openpyxl이 필요합니다: pip install openpyxl") from exc

        xlsx_path = Path(options["xlsx_path"])
        workbook = openpyxl.load_workbook(xlsx_path, data_only=True)

        placements = defaultdict(list)
        for row in _sheet_rows(workbook, "배치좌표"):
            key = (row["임시키"], _date(row["festival_date"]), row["time_slot"])
            placements[key].append(
                {
                    "unit_no": int(row["천막 번호"]),
                    "map_x": _number(row["map_x"]),
                    "map_y": _number(row["map_y"]),
                    "map_elevation": _number(row["map_elevation"]),
                    "rotation": _number(row["rotation"]),
                    "booth_size": row["booth_size"],
                    **_structure(row["구조물"]),
                }
            )

        operations = defaultdict(list)
        for row in _sheet_rows(workbook, "운영일정"):
            festival_date = _date(row["festival_date"])
            key = (row["임시키"], festival_date, row["time_slot"])
            operations[row["임시키"]].append(
                {
                    "festival_date": festival_date,
                    "time_slot": row["time_slot"],
                    "open_at": row["open_at"],
                    "close_at": row["close_at"],
                    "placements": sorted(placements.pop(key, []), key=lambda p: p["unit_no"]),
                }
            )
        if placements:
            orphans = ", ".join("/".join(key) for key in placements)
            raise CommandError(f"운영일정에 없는 배치좌표가 있습니다: {orphans}")

        # 'DB 반영'이 '포함'인 메뉴만 넣는다. 가격 미수령 행은 price NOT NULL이라 제외.
        menus = defaultdict(list)
        skipped_menus = 0
        for row in _sheet_rows(workbook, "메뉴"):
            if row["DB 반영"] != "포함":
                skipped_menus += 1
                continue
            menus[row["임시키"]].append(
                {"name": _text(row["메뉴명(name)"]), "price": int(row["price(원)"])}
            )

        booths = []
        for row in _sheet_rows(workbook, "부스"):
            key = row["임시키"]
            booths.append(
                {
                    "key": key,
                    "name": _text(row["name"]),
                    "subtitle": _text(row["subtitle"]),
                    "place_type": row["place_type"],
                    "category": row["category"],
                    "booth_size": row["booth_size"],
                    "zone": _text(row["zone"]),
                    "location_detail": _text(row["location_detail"]),
                    "map_x": _number(row["map_x"]),
                    "map_y": _number(row["map_y"]),
                    "map_elevation": _number(row["map_elevation"]),
                    "rotation": _number(row["rotation"]),
                    "description": _text(row["description"]),
                    "event_description": _text(row["event_description"]),
                    "instagram_id": _text(row["instagram_id"]),
                    "entrance_fee": row["entrance_fee"],
                    "has_reusable_container": bool(row["has_reusable_"]),
                    "operations": operations.pop(key, []),
                    "menus": menus.pop(key, []),
                }
            )
        if operations or menus:
            unknown = sorted({*operations, *menus})
            raise CommandError(f"부스 시트에 없는 임시키가 있습니다: {unknown}")

        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"source": xlsx_path.name, "booths": booths}
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        output.write_text(content, encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"{output} 저장 — 부스 {len(booths)} · "
                f"운영일정 {sum(len(b['operations']) for b in booths)} · "
                f"메뉴 {sum(len(b['menus']) for b in booths)} (가격 미수령 {skipped_menus}개 제외)"
            )
        )
