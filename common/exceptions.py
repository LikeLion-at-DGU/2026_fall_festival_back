"""API 에러 응답을 공통 형식으로 맞추기 위한 예외 정의.

이 예외 처리기는 프로젝트 전체에 적용하지 않고,
현재는 필요한 API에서만 직접 사용합니다.

전역 설정에 등록하면 쿠폰 API 등 다른 API의 에러 응답 형식까지
바뀔 수 있기 때문입니다.

추후 팀에서 전체 API의 에러 형식을 통일하기로 하면
REST_FRAMEWORK 설정에 등록해서 전역 적용할 수 있습니다.
"""

import logging

from rest_framework import status as http_status
from rest_framework.views import exception_handler as drf_exception_handler

from .responses import error_response

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """API에서 사용하는 기본 에러 클래스입니다."""

    status_code = http_status.HTTP_400_BAD_REQUEST
    code = "INVALID_INPUT"
    message = "입력값이 올바르지 않습니다."

    def __init__(self, message=None, errors=None, code=None, status_code=None):
        super().__init__(message or self.message)

        self.message = message or self.message
        self.errors = errors or {}

        if code is not None:
            self.code = code

        if status_code is not None:
            self.status_code = status_code


class InvalidInput(ApiError):
    """잘못된 입력값일 때 사용하는 에러입니다."""

    pass


class Unauthorized(ApiError):
    """관리자 인증이 없거나 올바르지 않을 때 사용하는 에러입니다."""

    status_code = http_status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"
    message = "관리자 인증이 필요합니다."


class NotFound(ApiError):
    """요청한 데이터를 찾을 수 없을 때 사용하는 에러입니다."""

    status_code = http_status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "요청한 리소스를 찾을 수 없습니다."


def custom_exception_handler(exc, context):
    """발생한 에러를 프로젝트의 공통 에러 응답 형식으로 변환합니다."""

    # 우리가 직접 만든 ApiError인 경우
    if isinstance(exc, ApiError):
        return error_response(
            exc.code,
            exc.message,
            exc.errors,
            status=exc.status_code,
        )

    # DRF에서 기본적으로 처리하는 에러인 경우
    response = drf_exception_handler(exc, context)

    # DRF에서도 처리하지 못한 예상치 못한 서버 에러
    if response is None:
        logger.exception("Unhandled server error")

        return error_response(
            "INTERNAL_ERROR",
            "서버 오류가 발생했습니다.",
            status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # DRF 에러 내용을 공통 응답 형식으로 변환
    detail = response.data

    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        errors = {}

    elif isinstance(detail, dict):
        message = "입력값이 올바르지 않습니다."
        errors = detail

    else:
        message = "요청을 처리할 수 없습니다."
        errors = {"detail": detail}

    # HTTP 상태 코드에 맞는 에러 코드 지정
    code = {
        400: "INVALID_INPUT",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }.get(response.status_code, "INTERNAL_ERROR")

    return error_response(
        code,
        message,
        errors,
        status=response.status_code,
    )
    
class FileTooLarge(ApiError):
    """파일 크기 제한 초과."""

    status_code = http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "FILE_TOO_LARGE"
    message = "허용된 파일 용량을 초과했습니다."


class UnsupportedFileType(ApiError):
    """지원하지 않는 파일 형식."""

    status_code = http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "UNSUPPORTED_FILE_TYPE"
    message = "지원하지 않는 이미지 형식입니다."
