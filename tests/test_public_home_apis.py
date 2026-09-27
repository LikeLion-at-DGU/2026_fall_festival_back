"""홈의 공개 데이터는 인증 상태와 무관하며 브라우저에 캐시하지 않는다."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import generate_jwt_token
from apps.booths.constants import DEFAULT_FESTIVAL_DATE
from apps.booths.models import Booth
from apps.lanterns.models import Lantern
from apps.performances.models import Performance

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_data():
    cache.clear()

    booth = Booth.objects.create(
        name="API 회귀검증 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
        lantern_count=17,
    )

    ranking_user = User.objects.create(
        kakao_id=809999,
        nickname="랭킹 회귀검증 사용자",
    )
    Lantern.objects.create(
        user=ranking_user,
        booth=booth,
        message="회귀검증 등불",
        festival_date=DEFAULT_FESTIVAL_DATE,
    )

    now = timezone.localtime()
    performance = Performance.objects.create(
        team_name="API 회귀검증 공연",
        festival_date=now.date(),
        start_at=now - timedelta(minutes=5),
        end_at=now + timedelta(minutes=30),
    )

    yield booth, performance

    cache.clear()


@pytest.mark.parametrize(
    "auth_mode",
    [
        "anonymous",
        "invalid",
        "valid",
    ],
)
def test_public_home_data_does_not_depend_on_jwt(
    public_data,
    auth_mode,
):
    booth, performance = public_data
    client = APIClient()

    if auth_mode == "invalid":
        client.credentials(
            HTTP_AUTHORIZATION="Bearer stale-access-token",
        )
    elif auth_mode == "valid":
        user = User.objects.create(
            kakao_id=801234,
            nickname="회귀검증 사용자",
        )
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {generate_jwt_token(user.pk)}",
        )

    ranking_response = client.get(
        "/api/booths/ranking/",
        {
            "date": DEFAULT_FESTIVAL_DATE.isoformat(),
            "limit": 3,
        },
    )

    assert ranking_response.status_code == 200

    ranking_data = ranking_response.json()["data"]
    ranking = ranking_data["ranking"]

    assert ranking_data["festival_date"] == DEFAULT_FESTIVAL_DATE.isoformat()
    assert ranking[0]["booth_id"] == booth.pk
    assert ranking[0]["lantern_count"] == 1

    now_response = client.get("/api/performances/now/")

    assert now_response.status_code == 200

    data = now_response.json()["data"]
    assert data["performances"][0]["performance_id"] == performance.pk
    assert data["performances"][0]["is_live"] is True
    assert data["server_time"]

    for response in [
        ranking_response,
        now_response,
    ]:
        assert "no-store" in response["Cache-Control"]
        assert "no-cache" in response["Cache-Control"]


def test_no_current_performances_is_a_successful_empty_response():
    response = APIClient().get("/api/performances/now/")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["performances"] == []
