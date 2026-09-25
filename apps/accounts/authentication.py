import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import User


class JWTAuthentication(BaseAuthentication):
    """
    JWT 토큰을 검증하는 클래스

    프론트가 보낸 Authorization 헤더에서 토큰을 꺼내고,
    그 토큰이 유효한지 검증한 후 request.user에 로그인 유저 정보를 담아줌
    """

    def authenticate(self, request):

        # Authorization 헤더에서 토큰 꺼내기/
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        try:
            prefix, token = auth_header.split(" ")
            if prefix != "Bearer":
                raise AuthenticationFailed("Invalid token prefix")
        except ValueError:
            raise AuthenticationFailed("Invalid Authorization header format") from None

        # 관리자 토큰인 경우 request.is_admin 설정 후 통과 (JWT decode 스킵)
        admin_expected = getattr(settings, "ADMIN_API_TOKEN", "")
        if admin_expected and token == admin_expected:
            request.is_admin = True
            return (None, token)

        # jwt.decode로 토큰 검증
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            # 토큰이 만료됐을 때
            raise AuthenticationFailed("Token expired") from None
        except jwt.InvalidTokenError:
            # 서명이 안 맞거나 형식이 잘못됐을 때
            raise AuthenticationFailed("Invalid token") from None

        # payload에서 user_id 꺼내고 유저 조회
        user_id = payload.get("user_id")

        if not user_id:
            raise AuthenticationFailed("Invalid token payload")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found") from None

        # (user, token) 반환
        return (user, token)

    def authenticate_header(self, request):
        return "Bearer"


class OptionalJWTAuthentication(JWTAuthentication):
    """공개 API의 개인화에만 사용하는 선택적 JWT 인증기.

    토큰이 없거나 유효하지 않아도 공개 데이터 조회 자체는 허용한다. 유효한 토큰일 때만
    ``request.user``를 채워 사용자별 필드를 계산한다. 인증이 필수인 API에는 사용하지 않는다.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None
