from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import JWTAuthentication
from apps.accounts.models import User

from .models import (
    BoothVerifyCode,
    Coupon,
    DailyCouponCounter,
    WinningNumber,
)
from .serializers import (
    CouponListItemSerializer,
    CouponSerializer,
    CouponStatsSerializer,
    CouponUseSerializer,
)

# 당첨된 쿠폰을 발급일 포함 며칠까지 사용(수령) 가능한지 (이슈 #80)
COUPON_VALID_DAYS = 3


# 쿠폰 발급
class CouponIssueView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["coupons"],
        summary="쿠폰 발급",
        description=(
            "로그인한 사용자에게 당일 쿠폰을 1개 발급합니다. "
            "사용자는 하루에 한 번만 쿠폰을 발급받을 수 있습니다."
        ),
        request=None,
        responses={
            201: CouponSerializer,
        },
    )
    @transaction.atomic
    def post(self, request):
        # JWT 인증을 통해 얻은 실제 로그인 유저
        user = User.objects.select_for_update().get(pk=request.user.pk)

        today = timezone.localdate()

        # 오늘 이미 쿠폰을 받은 적 있는지 확인
        already_issued = Coupon.objects.filter(
            user=user,
            issued_date=today,
        ).exists()

        if already_issued:
            return Response(
                {
                    "message": "오늘 이미 쿠폰을 발급받았습니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 오늘 날짜의 쿠폰 카운터 생성 또는 조회
        counter, created = DailyCouponCounter.objects.get_or_create(
            date=today,
            defaults={"count": 0},
        )

        # 동시에 여러 명이 발급받아도
        # 같은 daily_sequence가 생기지 않도록 잠금
        counter = DailyCouponCounter.objects.select_for_update().get(
            pk=counter.pk,
        )

        counter.count += 1
        counter.save(update_fields=["count"])

        # 쿠폰 생성
        coupon = Coupon.objects.create(
            user=user,
            issued_date=today,
            daily_sequence=counter.count,
            status=Coupon.Status.UNSCRATCHED,
        )

        return Response(
            CouponSerializer(coupon).data,
            status=status.HTTP_201_CREATED,
        )


# 쿠폰 긁기
class CouponScratchView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["coupons"],
        summary="쿠폰 스크래치 결과 확인",
        description=(
            "쿠폰의 당첨 여부를 확인합니다. "
            "이미 결과가 결정된 쿠폰은 기존 결과를 그대로 반환합니다."
        ),
        request=None,
        responses={
            200: CouponSerializer,
        },
    )
    @transaction.atomic
    def post(self, request, coupon_id):
        try:
            # 로그인한 본인의 쿠폰만 조회
            coupon = Coupon.objects.select_for_update().get(
                coupon_id=coupon_id,
                user=request.user,
                deleted_at__isnull=True,
            )

        except Coupon.DoesNotExist:
            return Response(
                {
                    "message": "존재하지 않거나 본인의 쿠폰이 아닙니다.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 미긁음 상태가 아니면 기존 상태와 결과를 그대로 반환
        if coupon.status != Coupon.Status.UNSCRATCHED:
            return Response(
                CouponSerializer(coupon).data,
                status=status.HTTP_200_OK,
            )

        # 당일 쿠폰만 스크래치 가능
        if coupon.issued_date != timezone.localdate():
            coupon.status = Coupon.Status.EXPIRED

            coupon.save(
                update_fields=[
                    "status",
                ]
            )

            data = CouponSerializer(coupon).data
            data["message"] = "기간이 만료된 쿠폰입니다."

            return Response(
                data,
                status=status.HTTP_400_BAD_REQUEST,
            )

        # daily_sequence가 당첨번호 DB에 존재하는지 확인
        is_win = WinningNumber.objects.filter(
            number=coupon.daily_sequence,
        ).exists()

        coupon.scratched_at = timezone.now()

        # 당첨
        if is_win:
            coupon.status = Coupon.Status.WIN

            coupon.save(
                update_fields=[
                    "status",
                    "scratched_at",
                ]
            )

            return Response(
                CouponSerializer(coupon).data,
                status=status.HTTP_200_OK,
            )

        # 꽝
        coupon.status = Coupon.Status.LOSE

        coupon.save(
            update_fields=[
                "status",
                "scratched_at",
            ]
        )

        return Response(
            CouponSerializer(coupon).data,
            status=status.HTTP_200_OK,
        )


# 나의 쿠폰 목록 조회
class CouponListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["coupons"],
        summary="내 쿠폰 목록 조회",
        description=(
            "로그인한 사용자가 보유한 쿠폰 목록을 조회합니다. "
            "status 쿼리 파라미터를 이용해 쿠폰 상태별로 필터링할 수 있습니다."
        ),
    )
    def get(self, request):
        # JWT의 로그인 유저가 가진 쿠폰만 조회
        coupons = Coupon.objects.filter(
            user=request.user,
            deleted_at__isnull=True,
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")

        if status_filter:
            coupons = coupons.filter(status=status_filter)

        items = CouponListItemSerializer(
            coupons,
            many=True,
        ).data

        return Response(
            {
                "success": True,
                "code": "COUPON_LIST_SUCCESS",
                "message": "쿠폰 목록을 조회했습니다.",
                "data": {
                    "total_count": len(items),
                    "items": items,
                },
            },
            status=status.HTTP_200_OK,
        )


# 쿠폰 사용 처리
class CouponUseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["coupons"],
        summary="쿠폰 사용 처리",
        description=("당첨된 쿠폰에 부스 확인 코드를 입력하여 사용 완료 상태로 변경합니다."),
        request=CouponUseSerializer,
    )
    @transaction.atomic
    def post(self, request, coupon_id):
        serializer = CouponUseSerializer(data=request.data)

        if not serializer.is_valid():
            errors = (
                {"verify_code": ("확인 코드를 입력해주세요.")}
                if "verify_code" in serializer.errors
                else serializer.errors
            )

            return Response(
                {
                    "success": False,
                    "code": "INVALID_INPUT",
                    "message": "필수 입력값이 누락되었습니다.",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verify_code = serializer.validated_data["verify_code"]

        try:
            # 로그인한 본인의 쿠폰만 조회
            coupon = Coupon.objects.select_for_update().get(
                coupon_id=coupon_id,
                user=request.user,
                deleted_at__isnull=True,
            )

        except Coupon.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "code": "COUPON_NOT_USABLE",
                    "message": "사용할 수 없는 쿠폰입니다.",
                    "errors": {"status": ("본인의 쿠폰이 아니거나 사용할 수 없는 쿠폰입니다.")},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 이미 사용된 쿠폰
        if coupon.status == Coupon.Status.USED:
            return Response(
                {
                    "success": False,
                    "code": "COUPON_ALREADY_USED",
                    "message": "이미 사용된 쿠폰입니다.",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 기간 만료 (발급일 포함 COUPON_VALID_DAYS일 이내만 사용 가능)
        if (
            coupon.status == Coupon.Status.EXPIRED
            or (timezone.localdate() - coupon.issued_date).days >= COUPON_VALID_DAYS
        ):
            return Response(
                {
                    "success": False,
                    "code": "COUPON_EXPIRED",
                    "message": ("사용 기간이 만료된 쿠폰입니다."),
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 당첨 쿠폰이 아님
        if coupon.status != Coupon.Status.WIN:
            return Response(
                {
                    "success": False,
                    "code": "COUPON_NOT_WIN",
                    "message": "당첨된 쿠폰이 아닙니다.",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 부스 확인 코드 검증
        matched_code = BoothVerifyCode.objects.filter(
            code=verify_code,
        ).first()

        if not matched_code:
            return Response(
                {
                    "success": False,
                    "code": "INVALID_VERIFY_CODE",
                    "message": "올바른 코드가 아닙니다.",
                    "errors": {
                        "verify_code": ("확인 코드가 일치하지 않습니다."),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon.status = Coupon.Status.USED
        coupon.used_at = timezone.now()

        coupon.save(
            update_fields=[
                "status",
                "used_at",
            ]
        )

        return Response(
            {
                "success": True,
                "code": "COUPON_USE_SUCCESS",
                "message": "쿠폰이 사용 처리되었습니다.",
                "data": {
                    "coupon_id": coupon.coupon_id,
                    "status": coupon.status,
                    "used_at": coupon.used_at,
                },
            },
            status=status.HTTP_200_OK,
        )


# 날짜별 쿠폰 발급/당첨 현황 조회
class CouponStatsView(APIView):
    @extend_schema(
        tags=["coupons"],
        summary="날짜별 쿠폰 발급 및 당첨 현황 조회",
        description=(
            "날짜별 쿠폰 발급 수와 당첨 수를 조회합니다. 사용 완료된 쿠폰도 당첨 수에 포함됩니다."
        ),
    )
    def get(self, request):
        counters = DailyCouponCounter.objects.all().order_by("date")

        stats = []

        for counter in counters:
            # USED도 원래 당첨된 쿠폰이므로 당첨 횟수에 포함
            win_count = Coupon.objects.filter(
                issued_date=counter.date,
                status__in=[
                    Coupon.Status.WIN,
                    Coupon.Status.USED,
                ],
                deleted_at__isnull=True,
            ).count()

            stats.append(
                {
                    "date": counter.date,
                    "issued_count": counter.count,
                    "win_count": win_count,
                }
            )

        serializer = CouponStatsSerializer(
            stats,
            many=True,
        )

        return Response(
            {
                "success": True,
                "code": "COUPON_STATS_SUCCESS",
                "message": ("쿠폰 발급 및 당첨 현황을 조회했습니다."),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
