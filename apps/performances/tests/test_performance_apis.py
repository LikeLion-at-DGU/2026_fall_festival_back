"""공연 조회 API 테스트 (#56)."""

from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone

from apps.performances import services
from apps.performances.models import Performance, Song

pytestmark = pytest.mark.django_db

LIST_URL = "/api/performances/"
NOW_URL = "/api/performances/now/"

DAY_1 = date(2026, 9, 29)
DAY_2 = date(2026, 9, 30)


def at(hour, minute=0, day=DAY_1):
    """축제 당일의 특정 시각을 서버 타임존 기준으로 만든다."""
    naive = datetime(day.year, day.month, day.day, hour, minute)
    return timezone.make_aware(naive)


def make_performance(
    *, team_name="음샘", festival_date=DAY_1, start_hour=16, end_hour=17, **kwargs
):
    return Performance.objects.create(
        team_name=team_name,
        festival_date=festival_date,
        start_at=at(start_hour, day=festival_date),
        end_at=at(end_hour, day=festival_date),
        **kwargs,
    )


class TestList:
    def test_empty_day_returns_200_with_empty_list(self, client):
        response = client.get(LIST_URL, {"date": "2026-09-29"})
        body = response.json()

        assert response.status_code == 200
        assert body["code"] == "PERFORMANCE_LIST_SUCCESS"
        assert body["data"]["performances"] == []
        assert body["data"]["festival_date"] == "2026-09-29"

    def test_returns_only_requested_day_ordered_by_start_at(self, client):
        make_performance(team_name="세번째", start_hour=18, end_hour=19)
        make_performance(team_name="첫번째", start_hour=16, end_hour=17)
        make_performance(team_name="둘째날", festival_date=DAY_2, start_hour=16, end_hour=17)

        body = client.get(LIST_URL, {"date": "2026-09-29"}).json()
        names = [item["team_name"] for item in body["data"]["performances"]]

        assert names == ["첫번째", "세번째"]

    def test_response_includes_server_time(self, client):
        # 기기 시계 오차 보정용이라 항상 내려가야 한다.
        body = client.get(LIST_URL, {"date": "2026-09-29"}).json()
        assert body["data"]["server_time"] is not None

    def test_date_outside_festival_is_rejected(self, client):
        response = client.get(LIST_URL, {"date": "2026-10-05"})
        body = response.json()

        assert response.status_code == 400
        assert body["code"] == "INVALID_FESTIVAL_DATE"
        assert "date" in body["errors"]

    def test_invalid_date_format_is_rejected(self, client):
        response = client.get(LIST_URL, {"date": "2026-99-99"})
        assert response.status_code == 400

    def test_soft_deleted_performance_is_excluded(self, client):
        performance = make_performance()
        performance.deleted_at = timezone.now()
        performance.save(update_fields=["deleted_at"])

        body = client.get(LIST_URL, {"date": "2026-09-29"}).json()
        assert body["data"]["performances"] == []

    def test_is_live_is_true_during_the_performance(self, client):
        # festival_date는 목록 조회용 날짜 컬럼이고, is_live 판정은 start_at/end_at을
        # 서버 시각과 비교한다. 그래서 실제 "지금"에 걸치도록 시각만 맞춘다.
        now = timezone.localtime()
        Performance.objects.create(
            team_name="진행중",
            festival_date=DAY_1,
            start_at=now - timedelta(minutes=10),
            end_at=now + timedelta(minutes=50),
        )

        body = client.get(LIST_URL, {"date": DAY_1.isoformat()}).json()
        assert body["data"]["performances"][0]["is_live"] is True

    def test_is_live_is_false_before_and_after(self, client):
        now = timezone.localtime()
        Performance.objects.create(
            team_name="끝남",
            festival_date=DAY_1,
            start_at=now - timedelta(hours=3),
            end_at=now - timedelta(hours=2),
        )
        Performance.objects.create(
            team_name="예정",
            festival_date=DAY_1,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3),
        )

        items = client.get(LIST_URL, {"date": DAY_1.isoformat()}).json()["data"]["performances"]
        assert all(item["is_live"] is False for item in items)


class TestDetail:
    def test_returns_songs_in_sort_order(self, client):
        performance = make_performance(affiliation="밴드동아리", description="출연진 소개")
        Song.objects.create(performance=performance, title="두번째곡", artist="B", sort_order=2)
        Song.objects.create(performance=performance, title="첫번째곡", artist="A", sort_order=1)

        response = client.get(f"{LIST_URL}{performance.pk}/")
        data = response.json()["data"]

        assert response.status_code == 200
        assert response.json()["code"] == "PERFORMANCE_DETAIL_SUCCESS"
        assert [song["title"] for song in data["songs"]] == ["첫번째곡", "두번째곡"]
        assert data["affiliation"] == "밴드동아리"
        assert data["description"] == "출연진 소개"

    def test_song_artist_can_be_null(self, client):
        performance = make_performance()
        Song.objects.create(performance=performance, title="제목만", artist=None, sort_order=1)

        data = client.get(f"{LIST_URL}{performance.pk}/").json()["data"]
        assert data["songs"][0]["artist"] is None

    def test_performance_without_songs_returns_empty_list(self, client):
        performance = make_performance()

        data = client.get(f"{LIST_URL}{performance.pk}/").json()["data"]
        assert data["songs"] == []

    def test_soft_deleted_song_is_excluded(self, client):
        performance = make_performance()
        Song.objects.create(performance=performance, title="살아있음", sort_order=1)
        deleted = Song.objects.create(performance=performance, title="지워짐", sort_order=2)
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=["deleted_at"])

        data = client.get(f"{LIST_URL}{performance.pk}/").json()["data"]
        assert [song["title"] for song in data["songs"]] == ["살아있음"]

    def test_unknown_id_returns_404(self, client):
        response = client.get(f"{LIST_URL}9999/")

        assert response.status_code == 404
        assert response.json()["code"] == "PERFORMANCE_NOT_FOUND"

    def test_soft_deleted_performance_returns_404(self, client):
        performance = make_performance()
        performance.deleted_at = timezone.now()
        performance.save(update_fields=["deleted_at"])

        assert client.get(f"{LIST_URL}{performance.pk}/").status_code == 404


class TestNow:
    """기획 판정 규칙 4가지를 전부 검증한다."""

    def test_live_performance_returns_live_plus_upcoming(self, client):
        now = timezone.localtime()
        Performance.objects.create(
            team_name="진행중",
            festival_date=DAY_1,
            start_at=now - timedelta(minutes=10),
            end_at=now + timedelta(minutes=50),
        )
        Performance.objects.create(
            team_name="다음",
            festival_date=DAY_1,
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=2),
        )

        body = client.get(NOW_URL).json()
        items = body["data"]["performances"]

        assert body["code"] == "PERFORMANCE_NOW_SUCCESS"
        assert [item["team_name"] for item in items] == ["진행중", "다음"]
        assert items[0]["is_live"] is True
        assert items[1]["is_live"] is False

    def test_returns_at_most_three(self, client):
        now = timezone.localtime()
        Performance.objects.create(
            team_name="진행중",
            festival_date=DAY_1,
            start_at=now - timedelta(minutes=10),
            end_at=now + timedelta(minutes=50),
        )
        for index in range(4):
            Performance.objects.create(
                team_name=f"예정{index}",
                festival_date=DAY_1,
                start_at=now + timedelta(hours=index + 1),
                end_at=now + timedelta(hours=index + 2),
            )

        items = client.get(NOW_URL).json()["data"]["performances"]
        assert len(items) == 3

    def test_upcoming_within_one_hour_is_previewed(self, client):
        # 진행 중은 없지만 첫 공연이 30분 뒤 → 미리보기로 보여준다.
        now = timezone.localtime()
        Performance.objects.create(
            team_name="곧시작",
            festival_date=DAY_1,
            start_at=now + timedelta(minutes=30),
            end_at=now + timedelta(minutes=90),
        )

        items = client.get(NOW_URL).json()["data"]["performances"]

        assert [item["team_name"] for item in items] == ["곧시작"]
        assert items[0]["is_live"] is False

    def test_upcoming_beyond_one_hour_returns_empty(self, client):
        # 첫 공연이 2시간 뒤 → 아직 보여주지 않는다.
        now = timezone.localtime()
        Performance.objects.create(
            team_name="멀었음",
            festival_date=DAY_1,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3),
        )

        assert client.get(NOW_URL).json()["data"]["performances"] == []

    def test_all_finished_returns_empty(self, client):
        now = timezone.localtime()
        Performance.objects.create(
            team_name="끝남",
            festival_date=DAY_1,
            start_at=now - timedelta(hours=3),
            end_at=now - timedelta(hours=2),
        )

        body = client.get(NOW_URL).json()

        assert body["data"]["performances"] == []
        assert body["data"]["server_time"] is not None

    def test_no_performances_at_all_returns_empty(self, client):
        assert client.get(NOW_URL).json()["data"]["performances"] == []


class TestDefaultDate:
    """날짜를 안 보냈을 때 어떤 날짜가 선택되는지.

    실제 "오늘"에 의존하면 축제 기간 중에 CI가 돌 때 결과가 달라지므로,
    날짜를 직접 넘길 수 있는 서비스 함수로 검증한다.
    """

    def test_today_is_used_during_the_festival(self):
        assert services.resolve_festival_date(None, date(2026, 9, 30)) == date(2026, 9, 30)

    def test_first_day_is_used_before_the_festival(self):
        assert services.resolve_festival_date(None, date(2026, 9, 1)) == DAY_1

    def test_first_day_is_used_after_the_festival(self):
        assert services.resolve_festival_date(None, date(2026, 12, 25)) == DAY_1

    def test_requested_date_always_wins(self):
        assert services.resolve_festival_date(DAY_2, date(2026, 9, 29)) == DAY_2

    def test_list_without_date_returns_200(self, client):
        assert client.get(LIST_URL).status_code == 200
        
class TestDateTimeFormat:
    """공연 시간 응답 형식을 검증한다."""

    def test_start_and_end_are_local_iso_without_timezone(
        self,
        client,
    ):
        make_performance(
            start_hour=16,
            end_hour=17,
        )

        body = client.get(
            LIST_URL,
            {"date": DAY_1.isoformat()},
        ).json()

        item = body["data"]["performances"][0]

        assert item["start_at"] == "2026-09-29T16:00:00"
        assert item["end_at"] == "2026-09-29T17:00:00"

    def test_server_time_has_no_timezone_suffix_or_microseconds(
        self,
        client,
    ):
        body = client.get(
            LIST_URL,
            {"date": DAY_1.isoformat()},
        ).json()

        server_time = body["data"]["server_time"]

        assert len(server_time) == 19
        assert not server_time.endswith("Z")
        assert "+" not in server_time
        assert "." not in server_time

    def test_detail_uses_same_datetime_format(
        self,
        client,
    ):
        performance = make_performance(
            start_hour=16,
            end_hour=17,
        )

        data = client.get(
            f"{LIST_URL}{performance.pk}/"
        ).json()["data"]

        assert data["start_at"] == "2026-09-29T16:00:00"
        assert data["end_at"] == "2026-09-29T17:00:00"
        assert data["festival_date"] == "2026-09-29"