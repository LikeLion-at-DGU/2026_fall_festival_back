"""공연 조회 API."""

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.clock import festival_now
from common.exceptions import InvalidInput, NotFound, custom_exception_handler
from common.responses import success_response
from common.schema import ErrorResponseSerializer

from . import selectors, services
from .serializers import (
    PerformanceDetailResponseSerializer,
    PerformanceListQuerySerializer,
    PerformanceListResponseSerializer,
    PerformanceNowResponseSerializer,
    to_detail,
    to_list_item,
    to_local_iso,
)


@method_decorator(never_cache, name="dispatch")
class PerformanceAPIView(APIView):
    """공연 API 공통 설정."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get_exception_handler(self):
        return custom_exception_handler


class PerformanceListView(PerformanceAPIView):
    """공연 타임테이블 조회 API."""

    @extend_schema(
        tags=["performances"],
        summary="공연 타임테이블 조회",
        operation_id="performance_list",
        parameters=[PerformanceListQuerySerializer],
        responses={
            200: PerformanceListResponseSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        query = PerformanceListQuerySerializer(data=request.query_params)

        if not query.is_valid():
            raise InvalidInput(
                code="INVALID_FESTIVAL_DATE",
                message="축제 기간 내의 날짜가 아닙니다.",
                errors={key: str(value[0]) for key, value in query.errors.items()},
            )

        now = festival_now()

        festival_date = services.resolve_festival_date(
            query.validated_data.get("date"),
            now.date(),
        )

        performances = selectors.list_performances_on(festival_date)

        return success_response(
            "PERFORMANCE_LIST_SUCCESS",
            "공연 목록을 조회했습니다.",
            {
                "festival_date": festival_date,
                "server_time": to_local_iso(now),
                "performances": [
                    to_list_item(
                        item,
                        is_live=services.is_live(item, now),
                    )
                    for item in performances
                ],
            },
        )


class PerformanceNowView(PerformanceAPIView):
    """지금 공연 중 조회 API."""

    @extend_schema(
        tags=["performances"],
        summary="지금 공연 중 조회",
        operation_id="performance_now",
        responses={
            200: PerformanceNowResponseSerializer,
        },
    )
    def get(self, request):
        now = festival_now()
        performances = services.now_playing_performances(now)

        return success_response(
            "PERFORMANCE_NOW_SUCCESS",
            "현재 공연 정보를 조회했습니다.",
            {
                "server_time": to_local_iso(now),
                "performances": [
                    to_list_item(
                        item,
                        is_live=services.is_live(item, now),
                    )
                    for item in performances
                ],
            },
        )


class PerformanceDetailView(PerformanceAPIView):
    """공연 상세 조회 API."""

    @extend_schema(
        tags=["performances"],
        summary="공연 상세 조회",
        operation_id="performance_detail",
        responses={
            200: PerformanceDetailResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, performance_id):
        performance = selectors.get_performance(performance_id)

        if performance is None:
            raise NotFound(
                code="PERFORMANCE_NOT_FOUND",
                message="공연을 찾을 수 없습니다.",
            )

        return success_response(
            "PERFORMANCE_DETAIL_SUCCESS",
            "공연 정보를 조회했습니다.",
            to_detail(performance),
        )
