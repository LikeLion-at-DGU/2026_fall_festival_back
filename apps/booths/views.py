"""Booths API views."""

from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.authentication import OptionalJWTAuthentication
from common.responses import error_response, success_response

from .constants import (
    CATEGORY_CHIPS,
    DAY_NIGHT_BOUNDARY,
    DEFAULT_FESTIVAL_DATE,
    FESTIVAL_DATES,
)
from .models import BoothOperation
from .selectors import (
    booth_detail,
    booth_operations_on,
    booth_ranking,
    booth_search,
    total_lantern_count,
)
from .serializers import (
    BoothDetailSerializer,
    BoothListItemSerializer,
    BoothSearchItemSerializer,
)


# 장소 목록 조회 (지도 핀 + 카드 리스트)
class BoothListView(APIView):
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request):
        now = timezone.localtime()

        # 날짜 탭 — 미지정 시 서버 오늘, 축제 기간 외면 첫날
        date_param = request.query_params.get("date")
        if date_param:
            try:
                festival_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            except ValueError:
                return error_response(
                    "INVALID_INPUT",
                    "잘못된 요청값입니다.",
                    {"date": "YYYY-MM-DD 형식으로 입력해주세요."},
                )
            if festival_date not in FESTIVAL_DATES:
                return error_response(
                    "INVALID_FESTIVAL_DATE",
                    "축제 기간 내의 날짜가 아닙니다.",
                    {"date": "2026-09-29 ~ 2026-10-01 중에서 선택해주세요."},
                )
        else:
            today = now.date()
            festival_date = today if today in FESTIVAL_DATES else DEFAULT_FESTIVAL_DATE

        # 주간/야간 탭 — 미지정 시 서버 시각 기준 (16:30 이전 DAY / 이후 NIGHT)
        time_slot = request.query_params.get("time_slot")
        if time_slot:
            if time_slot not in BoothOperation.TimeSlot.values:
                return error_response(
                    "INVALID_INPUT",
                    "잘못된 요청값입니다.",
                    {"time_slot": "DAY 또는 NIGHT 중에서 선택해주세요."},
                )
        else:
            time_slot = (
                BoothOperation.TimeSlot.DAY
                if now.time() < DAY_NIGHT_BOUNDARY
                else BoothOperation.TimeSlot.NIGHT
            )

        # 컬러칩 필터 — 미지정 시 전체. BOOTH 칩은 협업+일반 부스를 묶어서 반환
        category = request.query_params.get("category")
        if category and category not in CATEGORY_CHIPS:
            return error_response(
                "INVALID_INPUT",
                "잘못된 요청값입니다.",
                {"category": "BOOTH / TOILET / ALCOHOL / ECO 중에서 선택해주세요."},
            )

        operations = booth_operations_on(festival_date, time_slot, category, user=request.user)
        items = BoothListItemSerializer(operations, many=True).data

        return success_response(
            "BOOTH_LIST_SUCCESS",
            "장소 목록을 조회했습니다.",
            {
                "festival_date": festival_date.isoformat(),
                "time_slot": time_slot,
                "server_time": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_count": len(items),
                "booths": items,
            },
        )


# 장소 상세 조회 (부스 설명 바텀시트)
class BoothDetailView(APIView):
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, booth_id):
        booth = booth_detail(booth_id, user=request.user)

        if booth is None:
            return error_response(
                "BOOTH_NOT_FOUND",
                "장소를 찾을 수 없습니다.",
                status=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            "BOOTH_DETAIL_SUCCESS",
            "장소 정보를 조회했습니다.",
            BoothDetailSerializer(booth).data,
        )


# 장소 검색 (검색 모달)
class BoothSearchView(APIView):
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request):
        keyword = (request.query_params.get("keyword") or "").strip()
        if not keyword:
            return error_response(
                "INVALID_INPUT",
                "검색어를 입력해주세요.",
                {"keyword": "1자 이상 입력해주세요."},
            )
        if len(keyword) > 50:
            return error_response(
                "INVALID_INPUT",
                "잘못된 요청값입니다.",
                {"keyword": "50자 이하로 입력해주세요."},
            )

        # date 지정 시 해당 날짜에 운영 정보가 있는 부스만. 미지정 시 날짜 무관 전체
        festival_date = None
        date_param = request.query_params.get("date")
        if date_param:
            try:
                festival_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            except ValueError:
                return error_response(
                    "INVALID_INPUT",
                    "잘못된 요청값입니다.",
                    {"date": "YYYY-MM-DD 형식으로 입력해주세요."},
                )
            if festival_date not in FESTIVAL_DATES:
                return error_response(
                    "INVALID_FESTIVAL_DATE",
                    "축제 기간 내의 날짜가 아닙니다.",
                    {"date": "2026-09-29 ~ 2026-10-01 중에서 선택해주세요."},
                )

        # time_slot은 date와 함께 쓸 때만 사용 가능
        time_slot = request.query_params.get("time_slot")
        if time_slot:
            if time_slot not in BoothOperation.TimeSlot.values:
                return error_response(
                    "INVALID_INPUT",
                    "잘못된 요청값입니다.",
                    {"time_slot": "DAY 또는 NIGHT 중에서 선택해주세요."},
                )
            if festival_date is None:
                return error_response(
                    "INVALID_INPUT",
                    "잘못된 요청값입니다.",
                    {"time_slot": "time_slot은 date와 함께 사용해야 합니다."},
                )

        booths = booth_search(keyword, festival_date, time_slot, user=request.user)
        items = BoothSearchItemSerializer(booths, many=True).data

        return success_response(
            "BOOTH_SEARCH_SUCCESS",
            "장소를 검색했습니다.",
            {"keyword": keyword, "total_count": len(items), "booths": items},
        )


# 부스 등불 랭킹 (홈 화면)
class BoothRankingView(APIView):
    def get(self, request):
        limit_param = request.query_params.get("limit", "5")
        try:
            limit = int(limit_param)
        except ValueError:
            return error_response(
                "INVALID_INPUT",
                "잘못된 요청값입니다.",
                {"limit": "1~20 사이의 정수로 입력해주세요."},
            )
        if not 1 <= limit <= 20:
            return error_response(
                "INVALID_INPUT",
                "잘못된 요청값입니다.",
                {"limit": "1~20 사이의 정수로 입력해주세요."},
            )

        booths = booth_ranking(limit)

        # 동점은 같은 순위 (1, 1, 3 방식)
        ranking = []
        previous_count = None
        previous_rank = 0
        for position, booth in enumerate(booths, start=1):
            if booth.lantern_count != previous_count:
                previous_rank = position
                previous_count = booth.lantern_count

            ranking.append(
                {
                    "rank": previous_rank,
                    "booth_id": booth.id,
                    "name": booth.name,
                    "subtitle": booth.subtitle,
                    "thumbnail_url": booth.thumbnail_url,
                    "lantern_count": booth.lantern_count,
                }
            )

        return success_response(
            "BOOTH_RANKING_SUCCESS",
            "부스 랭킹을 조회했습니다.",
            {"total_lantern_count": total_lantern_count(), "ranking": ranking},
        )
