"""Notices API views."""

from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from common.exceptions import InvalidImageFile, InvalidInput, NotFound, custom_exception_handler
from common.pagination import paginate
from common.permissions import IsAdmin
from common.responses import success_response

from . import selectors, services
from .serializers import (
    AdminNoticeCreateSerializer,
    AdminNoticeDetailSerializer,
    AdminNoticeImageUploadResponseSerializer,
    AdminNoticeImageUploadSerializer,
    AdminNoticeListQuerySerializer,
    AdminNoticeUpdateSerializer,
    to_admin_notice_detail,
    to_admin_notice_list_item,
)


class AdminNoticeAPIView(APIView):
    """관리자 공지 API 기본 뷰."""

    permission_classes = [IsAdmin]

    def get_exception_handler(self):
        return custom_exception_handler


class AdminNoticeListView(AdminNoticeAPIView):
    """관리자 공지사항 목록 조회 (GET) 및 신규 등록 (POST) API."""

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 목록 조회",
        operation_id="admin_notice_list",
        parameters=[AdminNoticeListQuerySerializer],
    )
    def get(self, request):
        query_serializer = AdminNoticeListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=query_serializer.errors)

        notice_type = query_serializer.validated_data["type"]
        page = query_serializer.validated_data["page"]
        size = query_serializer.validated_data["size"]

        queryset = selectors.get_admin_notices_queryset(notice_type=notice_type)
        page_data = paginate(queryset, page=page, size=size)

        items = [to_admin_notice_list_item(notice) for notice in page_data.items]
        return success_response(
            "ADMIN_NOTICE_LIST_SUCCESS",
            "공지 목록 조회에 성공했습니다.",
            {
                "items": items,
                "meta": page_data.as_meta(),
            },
        )

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 신규 등록",
        operation_id="admin_notice_create",
        request=AdminNoticeCreateSerializer,
        responses={201: AdminNoticeDetailSerializer},
    )
    def post(self, request):
        serializer = AdminNoticeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=serializer.errors)

        notice = services.create_notice(
            title=serializer.validated_data["title"],
            content=serializer.validated_data["content"],
            type=serializer.validated_data.get("type", "NORMAL"),
            image_url=serializer.validated_data.get("image_url"),
            admin=getattr(request, "admin", None),
        )

        return success_response(
            "ADMIN_NOTICE_CREATE_SUCCESS",
            "공지사항이 성공적으로 등록되었습니다.",
            to_admin_notice_detail(notice),
            status=http_status.HTTP_201_CREATED,
        )


class AdminNoticeDetailView(AdminNoticeAPIView):
    """관리자 공지사항 상세 조회 (GET), 수정 (PUT), 삭제 (DELETE) API."""

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 상세 조회",
        operation_id="admin_notice_detail",
        responses={200: AdminNoticeDetailSerializer},
    )
    def get(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        return success_response(
            "ADMIN_NOTICE_DETAIL_SUCCESS",
            "공지 상세 조회에 성공했습니다.",
            to_admin_notice_detail(notice),
        )

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 수정",
        operation_id="admin_notice_update",
        request=AdminNoticeUpdateSerializer,
        responses={200: AdminNoticeDetailSerializer},
    )
    def put(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        serializer = AdminNoticeUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=serializer.errors)

        updated_notice = services.update_notice(
            notice,
            title=serializer.validated_data["title"],
            content=serializer.validated_data["content"],
            type=serializer.validated_data["type"],
            image_url=serializer.validated_data.get("image_url"),
        )

        return success_response(
            "ADMIN_NOTICE_UPDATE_SUCCESS",
            "공지사항이 성공적으로 수정되었습니다.",
            to_admin_notice_detail(updated_notice),
        )

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 삭제 (Soft Delete)",
        operation_id="admin_notice_delete",
        responses={200: None},
    )
    def delete(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        services.delete_notice(notice)

        return success_response(
            "ADMIN_NOTICE_DELETE_SUCCESS",
            "공지사항이 성공적으로 삭제되었습니다.",
            {},
        )


class AdminNoticeImageUploadView(AdminNoticeAPIView):
    """관리자 공지 이미지 업로드 API (POST /api/notices/images/)."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 이미지 업로드",
        operation_id="admin_notice_image_upload",
        request=AdminNoticeImageUploadSerializer,
        responses={201: AdminNoticeImageUploadResponseSerializer},
    )
    def post(self, request):
        serializer = AdminNoticeImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidImageFile(
                errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
            )

        image_file = serializer.validated_data["image"]
        image_url = services.upload_notice_image(image_file, request=request)

        return success_response(
            "IMAGE_UPLOAD_SUCCESS",
            "이미지가 성공적으로 업로드되었습니다.",
            {"image_url": image_url},
            status=http_status.HTTP_201_CREATED,
        )
