"""Lanterns API views."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.authentication import JWTAuthentication
from apps.booths.models import Booth
from common.clock import festival_localdate
from common.exceptions import (
    ApiError,
    InvalidInput,
    NotFound,
    Unauthorized,
    custom_exception_handler,
)
from common.pagination import paginate
from common.permissions import IsAdmin
from common.responses import success_response
from common.schema import ErrorResponseSerializer

from . import selectors, services
from .models import Lantern
from .serializers import (
    AdminLanternDeleteResponseSerializer,
    AdminLanternDetailResponseSerializer,
    AdminLanternListQuerySerializer,
    AdminLanternListResponseSerializer,
    LanternCreateResponseSerializer,
    LanternCreateSerializer,
    LanternDeleteResponseSerializer,
    LanternListQuerySerializer,
    LanternReportCreateSerializer,
    LanternReportResponseSerializer,
    LanternUpdateResponseSerializer,
    LanternUpdateSerializer,
    UserLanternDetailResponseSerializer,
    UserLanternListResponseSerializer,
    to_admin_lantern_detail,
    to_admin_lantern_list_item,
    to_lantern_item,
)


# --- User Views ---
class LanternViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = [JWTAuthentication]
    queryset = Lantern.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_exception_handler(self):
        return custom_exception_handler

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LanternCreateSerializer
        return LanternUpdateSerializer

    def get_object(self):
        try:
            obj = Lantern.objects.get(pk=self.kwargs["pk"])
        except Lantern.DoesNotExist as exc:
            raise NotFound(code="LANTERN_NOT_FOUND", message="존재하지 않는 등불입니다.") from exc

        if obj.user_id != self.request.user.id:
            raise ApiError(
                code="NOT_OWNER",
                message="본인이 작성한 등불만 수정·삭제할 수 있습니다.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if obj.deleted_at is not None:
            raise ApiError(
                code="ALREADY_DELETED",
                message="이미 삭제된 등불입니다.",
                status_code=status.HTTP_409_CONFLICT,
            )

        return obj

    @extend_schema(
        tags=["lanterns"],
        summary="등불 등록",
        description="새로운 등불을 등록합니다.",
        operation_id="user_lantern_create",
        request=LanternCreateSerializer,
        responses={
            201: LanternCreateResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput(
                code="INVALID_REQUEST_PARAM",
                message="요청 파라미터가 올바르지 않습니다.",
                errors={key: str(value[0]) for key, value in serializer.errors.items()},
            )
        serializer.save()
        return success_response(
            "LANTERN_CREATE_SUCCESS",
            "등불을 성공적으로 남겼어요!",
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["lanterns"],
        summary="등불 수정",
        description="내가 작성한 오늘의 등불을 수정합니다.",
        operation_id="user_lantern_update",
        request=LanternUpdateSerializer,
        responses={
            200: LanternUpdateResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        if instance.festival_date != festival_localdate():
            raise ApiError(
                code="NOT_TODAY_LANTERN",
                message="지난 등불은 수정할 수 없어요.",
                status_code=status.HTTP_409_CONFLICT,
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            raise InvalidInput(
                code="INVALID_REQUEST_PARAM",
                message="요청 파라미터가 올바르지 않습니다.",
                errors={key: str(value[0]) for key, value in serializer.errors.items()},
            )
        serializer.save()
        return success_response(
            "LANTERN_UPDATE_SUCCESS",
            "등불이 수정되었습니다.",
            serializer.data,
        )

    def perform_destroy(self, instance):
        now = timezone.now()
        with transaction.atomic():
            updated_rows = Lantern.objects.filter(id=instance.id, deleted_at__isnull=True).update(
                deleted_at=now, deleted_by=Lantern.DeletedBy.USER
            )

            if updated_rows == 0:
                raise ApiError(
                    code="ALREADY_DELETED",
                    message="이미 삭제된 등불입니다.",
                    status_code=status.HTTP_409_CONFLICT,
                )

            Booth.objects.filter(id=instance.booth_id).update(lantern_count=F("lantern_count") - 1)

    @extend_schema(
        tags=["lanterns"],
        summary="등불 삭제 (작성자 본인)",
        description="본인이 작성한 등불을 삭제합니다.",
        operation_id="user_lantern_delete",
        responses={
            200: LanternDeleteResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return success_response(
            code="LANTERN_DELETE_SUCCESS",
            message="등불이 삭제되었습니다.",
            data=None,
        )

    @extend_schema(
        tags=["lanterns"],
        summary="등불 목록 조회",
        description="부스별/일자별/내 등불 목록을 조회합니다.",
        operation_id="user_lantern_list",
        auth=[],
        parameters=[LanternListQuerySerializer],
        responses={
            200: UserLanternListResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def list(self, request, *args, **kwargs):
        query = LanternListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            raise InvalidInput(
                code="INVALID_REQUEST_PARAM",
                message="요청 파라미터가 올바르지 않습니다.",
                errors={key: str(value[0]) for key, value in query.errors.items()},
            )

        params = query.validated_data
        mine = params["mine"]

        if mine and request.user is None:
            raise Unauthorized(message="로그인이 필요합니다.")

        queryset = selectors.lantern_list_queryset(
            user=request.user,
            mine=mine,
            booth_id=params.get("booth_id"),
            festival_date=params.get("date"),
        )

        page = paginate(queryset, page=params["page"], size=params["size"])

        return success_response(
            "LANTERN_LIST_SUCCESS",
            "등불 목록을 조회했습니다.",
            {
                **page.as_meta(),
                "items": [to_lantern_item(item, request.user) for item in page.items],
            },
        )

    @extend_schema(
        tags=["lanterns"],
        summary="등불 상세 조회",
        description="등불 상세 정보를 조회합니다.",
        operation_id="user_lantern_detail",
        auth=[],
        responses={
            200: UserLanternDetailResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def retrieve(self, request, *args, **kwargs):
        lantern = selectors.get_lantern(self.kwargs["pk"])
        if lantern is None:
            raise NotFound(code="LANTERN_NOT_FOUND", message="존재하지 않는 등불입니다.")

        is_owner = request.user is not None and lantern.user_id == request.user.id
        if lantern.deleted_at is not None and not is_owner:
            raise NotFound(code="LANTERN_NOT_FOUND", message="존재하지 않는 등불입니다.")

        return success_response(
            "LANTERN_DETAIL_SUCCESS",
            "등불을 조회했습니다.",
            to_lantern_item(lantern, request.user),
        )

    @extend_schema(
        tags=["lanterns"],
        summary="등불 신고",
        description="부적절한 등불을 신고합니다.",
        operation_id="user_lantern_report",
        request=LanternReportCreateSerializer,
        responses={
            201: LanternReportResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    @action(detail=True, methods=["post"], url_path="reports")
    def report(self, request, pk=None):
        lantern = selectors.get_lantern(pk)
        if lantern is None or lantern.deleted_at is not None:
            raise NotFound(code="LANTERN_NOT_FOUND", message="존재하지 않는 등불입니다.")

        serializer = LanternReportCreateSerializer(
            data=request.data, context={"request": request, "lantern": lantern}
        )
        if not serializer.is_valid():
            raise InvalidInput(
                code="INVALID_REQUEST_PARAM",
                message="reason 값이 올바르지 않습니다.",
                errors={key: str(value[0]) for key, value in serializer.errors.items()},
            )
        serializer.save()

        return success_response(
            "LANTERN_REPORT_SUCCESS",
            "신고가 접수되었습니다.",
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


# --- Admin Views ---
class AdminLanternAPIView(APIView):
    """관리자 등불 API 기본 뷰."""

    permission_classes = [IsAdmin]

    def get_exception_handler(self):
        return custom_exception_handler


class AdminLanternListView(AdminLanternAPIView):
    """관리자 등불 목록 조회 API (GET /api/lanterns/)."""

    @extend_schema(
        tags=["admin-lanterns"],
        summary="관리자 등불 목록 조회",
        description=(
            "관리자 등불 목록을 조회합니다. "
            "신고 많은 순(REPORT_DESC) 또는 최신순(LATEST) 정렬을 지원합니다."
        ),
        operation_id="admin_lantern_list",
        parameters=[AdminLanternListQuerySerializer],
        responses={
            200: AdminLanternListResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        query_serializer = AdminLanternListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=query_serializer.errors)

        sort = query_serializer.validated_data["sort"]
        page = query_serializer.validated_data["page"]
        size = query_serializer.validated_data["size"]

        queryset = selectors.get_admin_lanterns_queryset(sort=sort)
        page_data = paginate(queryset, page=page, size=size)

        lantern_ids = [lantern.id for lantern in page_data.items]
        top_reasons = selectors.get_top_report_reasons_for_lanterns(lantern_ids)

        items = [
            to_admin_lantern_list_item(lantern, top_reasons.get(lantern.id))
            for lantern in page_data.items
        ]

        return success_response(
            "ADMIN_LANTERN_LIST_SUCCESS",
            "관리자 등불 목록 조회에 성공했습니다.",
            {
                "items": items,
                "meta": page_data.as_meta(),
            },
        )


class AdminLanternDetailView(AdminLanternAPIView):
    """관리자 등불 상세 조회 및 블라인드(삭제) API."""

    @extend_schema(
        tags=["admin-lanterns"],
        summary="관리자 등불 신고 상세 확인 (모달)",
        description=(
            "특정 등불의 최다 신고 사유, 총 신고 횟수, 부스 정보 및 등불 원문을 조회합니다."
        ),
        operation_id="admin_lantern_detail",
        responses={
            200: AdminLanternDetailResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, lantern_id: int):
        lantern = selectors.get_admin_lantern_by_id(lantern_id=lantern_id)
        if lantern is None:
            raise NotFound("해당 등불을 찾을 수 없습니다.")

        top_reasons = selectors.get_top_report_reasons_for_lanterns([lantern.id])
        top_reason = top_reasons.get(lantern.id)

        return success_response(
            "ADMIN_LANTERN_DETAIL_SUCCESS",
            "관리자 등불 신고 상세 조회에 성공했습니다.",
            to_admin_lantern_detail(lantern, top_reason),
        )

    @extend_schema(
        tags=["admin-lanterns"],
        summary="관리자 등불 삭제 (블라인드 처리)",
        description=(
            "관리자 권한으로 부적절한 등불을 블라인드(Soft Delete) 처리하고 "
            "연관 부스의 등불 수를 1 차감합니다."
        ),
        operation_id="admin_lantern_delete",
        responses={
            200: AdminLanternDeleteResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def delete(self, request, lantern_id: int):
        lantern = selectors.get_admin_lantern_by_id(lantern_id=lantern_id)
        if lantern is None:
            raise NotFound("해당 등불을 찾을 수 없습니다.")

        services.delete_admin_lantern(lantern)

        return success_response(
            "ADMIN_LANTERN_DELETE_SUCCESS",
            "등불이 성공적으로 삭제되었습니다.",
            {},
        )
