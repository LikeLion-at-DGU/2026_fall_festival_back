"""분실물 API.

- 관리자용: 목록/상세 조회, 등록, 수정, 삭제
- 사용자용: 목록/상세 조회 (읽기 전용)
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.exceptions import InvalidInput, NotFound, custom_exception_handler
from common.pagination import paginate
from common.permissions import IsAdmin
from common.responses import success_response
from common.schema import ErrorResponseSerializer

from . import selectors, services
from .serializers import (
    LostItemDeleteResponseSerializer,
    LostItemDetailResponseSerializer,
    LostItemIdResponseSerializer,
    LostItemImageUploadRequestSerializer,
    LostItemImageUploadResponseSerializer,
    LostItemListQuerySerializer,
    LostItemListResponseSerializer,
    LostItemUpdateResponseSerializer,
    LostItemWriteSerializer,
    UserLostItemDetailResponseSerializer,
    UserLostItemListQuerySerializer,
    to_detail,
    to_list_item,
    to_user_detail,
)


class AdminLostItemAPIView(APIView):
    """분실물 관리자 API들이 공통으로 상속하는 베이스 뷰.

    get_exception_handler()를 오버라이드해서 공통 에러 응답 형식
    ({success, code, message, errors})을 "이 앱에만" 적용한다.
    REST_FRAMEWORK 설정에 전역으로 등록하지 않은 이유는, 그렇게 하면 쿠폰 API 등
    이미 DRF 기본 에러 형식을 쓰고 있는 다른 곳도 전부 영향을 받기 때문이다.
    팀에서 전체 통일하기로 하면 common/exceptions.py의 함수를 전역 설정으로
    옮기기만 하면 된다.
    """

    def get_exception_handler(self):
        return custom_exception_handler


class AdminLostItemListView(AdminLostItemAPIView):
    """GET /api/admin/lost-items/"""

    permission_classes = [IsAdmin]

    @extend_schema(
        tags=["admin-lost-items"],
        summary="분실물 목록 조회 (관리자)",
        operation_id="admin_lost_item_list",
        parameters=[LostItemListQuerySerializer],
        responses={
            200: LostItemListResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        query = LostItemListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            raise InvalidInput(errors={key: str(value[0]) for key, value in query.errors.items()})

        params = query.validated_data
        page = paginate(
            selectors.list_lost_items(found_date=params.get("found_date")),
            page=params["page"],
            size=params["size"],
        )

        return success_response(
            "LOST_ITEM_LIST_SUCCESS",
            "분실물 목록을 조회했습니다.",
            {**page.as_meta(), "items": [to_list_item(item) for item in page.items]},
        )

    @extend_schema(
        tags=["admin-lost-items"],
        summary="분실물 등록 (관리자)",
        operation_id="admin_lost_item_create",
        request=LostItemWriteSerializer,
        responses={
            201: LostItemIdResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = LostItemWriteSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput(
                errors={key: str(value[0]) for key, value in serializer.errors.items()}
            )

        lost_item = services.create_lost_item(
            **serializer.validated_data,
            admin_id=getattr(request, "admin_id", None),
        )
        return success_response(
            "LOST_ITEM_CREATE_SUCCESS",
            "분실물을 등록했습니다.",
            {"lost_item_id": lost_item.pk},
            status=http_status.HTTP_201_CREATED,
        )


class AdminLostItemDetailView(AdminLostItemAPIView):
    """분실물 상세 조회, 수정 및 삭제 API."""

    permission_classes = [IsAdmin]

    @extend_schema(
        tags=["admin-lost-items"],
        summary="분실물 상세 조회 (관리자)",
        operation_id="admin_lost_item_detail",
        responses={
            200: LostItemDetailResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, lost_item_id):
        lost_item = selectors.get_lost_item(lost_item_id)
        if lost_item is None:
            raise NotFound(code="LOST_ITEM_NOT_FOUND", message="분실물을 찾을 수 없습니다.")

        return success_response(
            "LOST_ITEM_DETAIL_SUCCESS",
            "분실물 정보를 조회했습니다.",
            to_detail(lost_item),
        )

    @extend_schema(
        tags=["admin-lost-items"],
        summary="분실물 수정 (관리자)",
        operation_id="admin_lost_item_update",
        request=LostItemWriteSerializer,
        responses={
            200: LostItemUpdateResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def put(self, request, lost_item_id):
        lost_item = selectors.get_lost_item(lost_item_id)
        if lost_item is None:
            raise NotFound(code="LOST_ITEM_NOT_FOUND", message="분실물을 찾을 수 없습니다.")

        serializer = LostItemWriteSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput(
                errors={key: str(value[0]) for key, value in serializer.errors.items()}
            )

        services.update_lost_item(lost_item, **serializer.validated_data)

        # 이미지·태그가 replace-all로 바뀌었으니, lost_item에 캐시된
        # alive_images/alive_tags가 아니라 새로 조회한 상태로 응답한다.
        updated_item = selectors.get_lost_item(lost_item_id)
        return success_response(
            "LOST_ITEM_UPDATE_SUCCESS",
            "분실물 정보를 수정했습니다.",
            to_detail(updated_item),
        )

    @extend_schema(
        tags=["admin-lost-items"],
        summary="분실물 삭제 (관리자)",
        operation_id="admin_lost_item_delete",
        responses={
            200: LostItemDeleteResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def delete(self, request, lost_item_id):
        # 삭제할 분실물 조회
        lost_item = selectors.get_lost_item(lost_item_id)
        if lost_item is None:
            raise NotFound(code="LOST_ITEM_NOT_FOUND", message="분실물을 찾을 수 없습니다.")

        # 분실물과 이미지, 태그 Soft Delete
        deleted_at = services.delete_lost_item(lost_item)

        return success_response(
            "LOST_ITEM_DELETE_SUCCESS",
            "분실물을 삭제했습니다.",
            {"lost_item_id": lost_item.pk, "deleted_at": deleted_at},
        )


class AdminLostItemImageUploadView(AdminLostItemAPIView):
    """관리자 분실물 이미지 업로드 API."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["admin-lost-items"],
        summary="분실물 이미지 업로드 (관리자)",
        operation_id="admin_lost_item_image_upload",
        request=LostItemImageUploadRequestSerializer,
        responses={
            201: LostItemImageUploadResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            413: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = LostItemImageUploadRequestSerializer(data=request.data)

        if not serializer.is_valid():
            raise InvalidInput(
                errors={
                    key: str(value[0])
                    for key, value in serializer.errors.items()
                }
            )

        # 파일 검증 및 저장
        storage_url = services.store_image(serializer.validated_data["file"])

        # 클라이언트에서 바로 사용할 수 있도록 절대 URL 생성
        image_url = request.build_absolute_uri(storage_url)

        return success_response(
            "LOST_ITEM_IMAGE_UPLOAD_SUCCESS",
            "이미지를 업로드했습니다.",
            {"image_url": image_url},
            status=http_status.HTTP_201_CREATED,
        )

class LostItemAPIView(APIView):
    """사용자용 View의 기본 클래스"""

    permission_classes = [AllowAny]

    def get_exception_handler(self):
        return custom_exception_handler


class UserLostItemListView(LostItemAPIView):
    """GET /api/lost-items/ (사용자 분실물 목록 조회)"""

    @extend_schema(
        tags=["lost-items"],
        summary="분실물 목록 조회 (사용자)",
        operation_id="user_lost_item_list",
        parameters=[UserLostItemListQuerySerializer],
        responses={
            200: LostItemListResponseSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        query = UserLostItemListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            raise InvalidInput(errors={key: str(value[0]) for key, value in query.errors.items()})

        params = query.validated_data
        page = paginate(
            selectors.list_lost_items(
                found_date=params.get("found_date"),
                keyword=params.get("keyword"),
            ),
            page=params["page"],
            size=params["size"],
        )

        return success_response(
            "LOST_ITEM_LIST_SUCCESS",
            "분실물 목록을 조회했습니다.",
            {**page.as_meta(), "items": [to_list_item(item) for item in page.items]},
        )


class UserLostItemDetailView(LostItemAPIView):
    """GET /api/lost-items/{lost_item_id}/ (사용자 분실물 상세 조회)"""

    @extend_schema(
        tags=["lost-items"],
        summary="분실물 상세 조회 (사용자)",
        operation_id="user_lost_item_detail",
        responses={
            200: UserLostItemDetailResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, lost_item_id):
        lost_item = selectors.get_lost_item(lost_item_id)
        if lost_item is None:
            raise NotFound(code="LOST_ITEM_NOT_FOUND", message="해당 분실물을 찾을 수 없습니다.")

        return success_response(
            "LOST_ITEM_DETAIL_SUCCESS",
            "분실물 상세 정보를 조회했습니다.",
            to_user_detail(lost_item),
        )