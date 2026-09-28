"""Lantern registration/update/delete API tests."""

from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booths.models import Booth, BoothOperation
from apps.lanterns.models import Lantern
from apps.lanterns.serializers import LanternCreateSerializer, LanternUpdateSerializer
from apps.lanterns.views import LanternViewSet
from common.exceptions import ApiError

FESTIVAL_DAY = date(2026, 9, 29)
OUT_OF_FESTIVAL_DAY = date(2026, 9, 1)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(kakao_id=1001, nickname="테스트유저")


@pytest.fixture
def other_user(db):
    return User.objects.create(kakao_id=1002, nickname="다른유저")


@pytest.fixture
def booth(db):
    booth = Booth.objects.create(
        name="테스트 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )
    _add_operation(booth)
    return booth


@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client


def _patch_today(target_date=FESTIVAL_DAY):
    return patch("apps.lanterns.serializers.timezone.localdate", return_value=target_date)


def _patch_today_views(target_date=FESTIVAL_DAY):
    return patch("apps.lanterns.views.timezone.localdate", return_value=target_date)


def _add_operation(
    booth,
    *,
    festival_date=FESTIVAL_DAY,
    time_slot=BoothOperation.TimeSlot.DAY,
    deleted_at=None,
):
    return BoothOperation.objects.create(
        booth=booth,
        festival_date=festival_date,
        time_slot=time_slot,
        open_at=time(10, 0),
        close_at=time(22, 0),
        deleted_at=deleted_at,
    )


@pytest.mark.django_db
class TestLanternBoothOptions:
    def test_returns_all_booths_operating_today_regardless_of_time_slot(self, client):
        day_booth = Booth.objects.create(
            name="가 주간 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
        )
        night_booth = Booth.objects.create(
            name="나 야간 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ALCOHOL,
        )
        both_booth = Booth.objects.create(
            name="다 종일 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.COLLAB,
        )
        _add_operation(day_booth, time_slot=BoothOperation.TimeSlot.DAY)
        _add_operation(night_booth, time_slot=BoothOperation.TimeSlot.NIGHT)
        _add_operation(both_booth, time_slot=BoothOperation.TimeSlot.DAY)
        _add_operation(both_booth, time_slot=BoothOperation.TimeSlot.NIGHT)

        with patch("apps.lanterns.views.festival_localdate", return_value=FESTIVAL_DAY):
            response = client.get("/api/lanterns/booth-options/")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "LANTERN_BOOTH_OPTIONS_SUCCESS"
        assert body["data"]["festival_date"] == "2026-09-29"
        assert body["data"]["booths"] == [
            {"booth_id": day_booth.id, "name": "가 주간 부스", "category": "ETC"},
            {"booth_id": night_booth.id, "name": "나 야간 부스", "category": "ALCOHOL"},
            {"booth_id": both_booth.id, "name": "다 종일 부스", "category": "COLLAB"},
        ]

    def test_excludes_ineligible_booths(self, client):
        other_day = Booth.objects.create(
            name="다른 날짜 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
        )
        deleted_operation = Booth.objects.create(
            name="운영 삭제 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
        )
        deleted_booth = Booth.objects.create(
            name="삭제 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
            deleted_at=timezone.now(),
        )
        facility = Booth.objects.create(
            name="화장실",
            place_type=Booth.PlaceType.FACILITY,
            category=Booth.Category.TOILET,
        )
        _add_operation(other_day, festival_date=date(2026, 9, 30))
        _add_operation(deleted_operation, deleted_at=timezone.now())
        _add_operation(deleted_booth)
        _add_operation(facility)

        with patch("apps.lanterns.views.festival_localdate", return_value=FESTIVAL_DAY):
            response = client.get("/api/lanterns/booth-options/")

        assert response.status_code == 200
        assert response.json()["data"]["booths"] == []


@pytest.mark.django_db
class TestLanternCreate:
    def test_create_success(self, auth_client, user, booth):
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "화이팅!"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["code"] == "LANTERN_CREATE_SUCCESS"
        assert body["data"]["booth_id"] == booth.id
        assert body["data"]["nickname"] == "익명의 코끼리"
        assert body["data"]["message"] == "화이팅!"
        assert body["data"]["festival_date"] == "2026-09-29"
        assert body["data"]["is_first_today"] is True

        booth.refresh_from_db()
        assert booth.lantern_count == 1
        assert Lantern.objects.filter(user=user, booth=booth).count() == 1

    def test_create_marks_is_first_today_false_for_second_lantern(self, auth_client, user, booth):
        Lantern.objects.create(
            user=user, booth=booth, message="첫 등불", festival_date=FESTIVAL_DAY
        )

        other_booth = Booth.objects.create(
            name="다른 부스", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
        )
        _add_operation(other_booth)
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": other_booth.id, "message": "두번째!"},
            )

        assert response.status_code == 201
        assert response.json()["data"]["is_first_today"] is False

    def test_create_with_nickname(self, auth_client, booth):
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "nickname": "코끼리", "message": "화이팅!"},
            )
        assert response.status_code == 201
        assert response.json()["data"]["nickname"] == "코끼리"

    def test_create_with_blank_nickname_defaults(self, auth_client, booth):
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "nickname": "", "message": "화이팅!"},
            )
        assert response.status_code == 201
        assert response.json()["data"]["nickname"] == "익명의 코끼리"

    def test_create_rejects_outside_festival_period(self, auth_client, booth):
        with _patch_today(OUT_OF_FESTIVAL_DAY):
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "화이팅!"},
            )
        assert response.status_code == 400
        assert response.json()["code"] == "NOT_FESTIVAL_PERIOD"

    def test_create_rejects_missing_booth(self, auth_client):
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": 999999, "message": "화이팅!"},
            )
        assert response.status_code == 404
        assert response.json()["code"] == "BOOTH_NOT_FOUND"

    def test_create_rejects_facility_place_type(self, auth_client, db):
        facility = Booth.objects.create(
            name="화장실",
            place_type=Booth.PlaceType.FACILITY,
            category=Booth.Category.TOILET,
        )
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": facility.id, "message": "화이팅!"},
            )
        assert response.status_code == 404
        assert response.json()["code"] == "BOOTH_NOT_FOUND"

    def test_create_rejects_booth_not_operating_today(self, auth_client, db):
        booth = Booth.objects.create(
            name="오늘 미운영 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
        )
        _add_operation(booth, festival_date=date(2026, 9, 30))

        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "화이팅!"},
            )

        assert response.status_code == 404
        assert response.json()["code"] == "BOOTH_NOT_FOUND"

    @pytest.mark.parametrize(
        "time_slot",
        [BoothOperation.TimeSlot.DAY, BoothOperation.TimeSlot.NIGHT],
    )
    def test_create_accepts_booth_with_any_time_slot(self, auth_client, db, time_slot):
        operating_booth = Booth.objects.create(
            name=f"{time_slot} 전용 부스",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ETC,
        )
        _add_operation(operating_booth, time_slot=time_slot)

        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": operating_booth.id, "message": "시간대 무관"},
            )

        assert response.status_code == 201

    def test_create_rejects_duplicate_same_day(self, auth_client, user, booth):
        Lantern.objects.create(user=user, booth=booth, message="먼저", festival_date=FESTIVAL_DAY)
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "화이팅!"},
            )
        assert response.status_code == 409
        assert response.json()["code"] == "DUPLICATE_BOOTH_LANTERN"

    def test_create_allows_reregistration_after_delete(self, auth_client, user, booth):
        deleted = Lantern.objects.create(
            user=user, booth=booth, message="먼저", festival_date=FESTIVAL_DAY
        )
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = Lantern.DeletedBy.USER
        deleted.save()

        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "다시 달았어요"},
            )
        assert response.status_code == 201

    def test_create_rejects_daily_limit_exceeded(self, auth_client, user, db):
        for i in range(3):
            b = Booth.objects.create(
                name=f"부스{i}", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
            )
            Lantern.objects.create(user=user, booth=b, message="등불", festival_date=FESTIVAL_DAY)

        extra_booth = Booth.objects.create(
            name="네번째 부스", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
        )
        _add_operation(extra_booth)
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": extra_booth.id, "message": "화이팅!"},
            )
        assert response.status_code == 409
        assert response.json()["code"] == "DAILY_LIMIT_EXCEEDED"

    def test_create_rejects_forbidden_word(self, auth_client, booth):
        with (
            _patch_today(),
            patch("apps.lanterns.serializers.contains_forbidden_word", return_value=True),
        ):
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "아무말"},
            )
        assert response.status_code == 400
        assert response.json()["code"] == "FORBIDDEN_WORD_DETECTED"

    def test_create_requires_authentication(self, client, booth):
        response = client.post("/api/lanterns/", {"booth_id": booth.id, "message": "화이팅!"})
        assert response.status_code in (401, 403)

    def test_create_rejects_invalid_field_value(self, auth_client, booth):
        with _patch_today():
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "x" * 31},
            )
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_REQUEST_PARAM"

    def test_create_rejects_forbidden_nickname(self, auth_client, booth):
        with (
            _patch_today(),
            patch("apps.lanterns.serializers.contains_forbidden_word", return_value=True),
        ):
            response = auth_client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "nickname": "나쁜말", "message": "화이팅!"},
            )
        assert response.status_code == 400
        assert response.json()["code"] == "FORBIDDEN_WORD_DETECTED"

    def test_create_with_real_jwt_token(self, client, user, booth):
        import jwt
        from django.conf import settings

        token = jwt.encode({"user_id": user.id}, settings.SECRET_KEY, algorithm="HS256")
        with _patch_today():
            response = client.post(
                "/api/lanterns/",
                {"booth_id": booth.id, "message": "화이팅!"},
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
        assert response.status_code == 201
        assert response.json()["code"] == "LANTERN_CREATE_SUCCESS"

    def test_create_handles_race_duplicate_booth(self, user, booth):
        with _patch_today():
            today = timezone.localdate()
            Lantern.objects.create(user=user, booth=booth, message="선점", festival_date=today)

            serializer = LanternCreateSerializer(context={"request": SimpleNamespace(user=user)})
            serializer._today = today

            with pytest.raises(ApiError) as exc_info:
                serializer.create(
                    {"booth_id": booth.id, "nickname": "익명의 코끼리", "message": "화이팅!"}
                )

        assert exc_info.value.code == "DUPLICATE_BOOTH_LANTERN"

    def test_create_recheck_blocks_daily_limit_under_lock(self, user, db):
        with _patch_today():
            today = timezone.localdate()
            for i in range(3):
                b = Booth.objects.create(
                    name=f"락테스트부스{i}",
                    place_type=Booth.PlaceType.BOOTH,
                    category=Booth.Category.ETC,
                )
                Lantern.objects.create(user=user, booth=b, message="등불", festival_date=today)

            extra_booth = Booth.objects.create(
                name="락테스트여분부스",
                place_type=Booth.PlaceType.BOOTH,
                category=Booth.Category.ETC,
            )

            serializer = LanternCreateSerializer(context={"request": SimpleNamespace(user=user)})
            serializer._today = today

            with pytest.raises(ApiError) as exc_info:
                serializer.create(
                    {"booth_id": extra_booth.id, "nickname": "익명의 코끼리", "message": "화이팅!"}
                )

        assert exc_info.value.code == "DAILY_LIMIT_EXCEEDED"

    def test_create_computes_is_first_today_from_locked_recheck(self, user, booth):
        with _patch_today():
            today = timezone.localdate()
            Lantern.objects.create(user=user, booth=booth, message="선점", festival_date=today)

            other_booth = Booth.objects.create(
                name="락체크부스",
                place_type=Booth.PlaceType.BOOTH,
                category=Booth.Category.ETC,
            )

            serializer = LanternCreateSerializer(context={"request": SimpleNamespace(user=user)})
            serializer._today = today
            serializer._is_first_today = True

            serializer.create(
                {"booth_id": other_booth.id, "nickname": "익명의 코끼리", "message": "두번째!"}
            )

        assert serializer._is_first_today is False


@pytest.mark.django_db
class TestLanternUpdate:
    def test_update_success(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="원래 메시지", festival_date=FESTIVAL_DAY
        )
        with _patch_today_views():
            response = auth_client.patch(
                f"/api/lanterns/{lantern.id}/", {"message": "수정된 메시지"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "LANTERN_UPDATE_SUCCESS"
        assert body["data"]["message"] == "수정된 메시지"

        lantern.refresh_from_db()
        assert lantern.message == "수정된 메시지"

    def test_update_rejects_not_owner(self, auth_client, other_user, booth):
        lantern = Lantern.objects.create(
            user=other_user, booth=booth, message="다른 사람 등불", festival_date=FESTIVAL_DAY
        )
        response = auth_client.patch(f"/api/lanterns/{lantern.id}/", {"message": "수정 시도"})
        assert response.status_code == 403
        assert response.json()["code"] == "NOT_OWNER"

    def test_update_rejects_missing_lantern(self, auth_client):
        response = auth_client.patch("/api/lanterns/999999/", {"message": "수정 시도"})
        assert response.status_code == 404
        assert response.json()["code"] == "LANTERN_NOT_FOUND"

    def test_update_rejects_already_deleted(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="삭제될 등불", festival_date=FESTIVAL_DAY
        )
        lantern.deleted_at = timezone.now()
        lantern.deleted_by = Lantern.DeletedBy.USER
        lantern.save()

        response = auth_client.patch(f"/api/lanterns/{lantern.id}/", {"message": "수정 시도"})
        assert response.status_code == 409
        assert response.json()["code"] == "ALREADY_DELETED"

    def test_update_is_safe_under_concurrent_delete(self, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="원래 메시지", festival_date=FESTIVAL_DAY
        )

        Lantern.objects.filter(id=lantern.id).update(
            deleted_at=timezone.now(), deleted_by=Lantern.DeletedBy.USER
        )

        serializer = LanternUpdateSerializer(lantern, data={"message": "수정 시도"}, partial=True)
        assert serializer.is_valid(), serializer.errors

        with pytest.raises(ApiError) as exc_info:
            serializer.save()

        assert exc_info.value.code == "ALREADY_DELETED"

        lantern.refresh_from_db()
        assert lantern.message == "원래 메시지"

    def test_update_bumps_updated_at(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="원래 메시지", festival_date=FESTIVAL_DAY
        )
        original_updated_at = lantern.updated_at

        with _patch_today_views():
            response = auth_client.patch(
                f"/api/lanterns/{lantern.id}/", {"message": "수정된 메시지"}
            )
        assert response.status_code == 200

        lantern.refresh_from_db()
        assert lantern.updated_at > original_updated_at

    def test_update_rejects_not_today(self, auth_client, user, booth):
        # 10-4: 당일 작성한 등불만 수정 가능, 지난 날짜 등불은 삭제만 가능
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="어제 등불", festival_date=OUT_OF_FESTIVAL_DAY
        )
        with _patch_today_views():
            response = auth_client.patch(f"/api/lanterns/{lantern.id}/", {"message": "수정 시도"})
        assert response.status_code == 409
        assert response.json()["code"] == "NOT_TODAY_LANTERN"

    def test_update_rejects_forbidden_word(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="원래 메시지", festival_date=FESTIVAL_DAY
        )
        with (
            _patch_today_views(),
            patch("apps.lanterns.serializers.contains_forbidden_word", return_value=True),
        ):
            response = auth_client.patch(f"/api/lanterns/{lantern.id}/", {"message": "나쁜말"})
        assert response.status_code == 400
        assert response.json()["code"] == "FORBIDDEN_WORD_DETECTED"

    def test_update_rejects_invalid_field_value(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="원래 메시지", festival_date=FESTIVAL_DAY
        )
        with _patch_today_views():
            response = auth_client.patch(f"/api/lanterns/{lantern.id}/", {"message": "x" * 31})
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_REQUEST_PARAM"

    def test_update_rejects_forbidden_nickname(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="원래 메시지", festival_date=FESTIVAL_DAY
        )
        with (
            _patch_today_views(),
            patch("apps.lanterns.serializers.contains_forbidden_word", return_value=True),
        ):
            response = auth_client.patch(f"/api/lanterns/{lantern.id}/", {"nickname": "나쁜말"})
        assert response.status_code == 400
        assert response.json()["code"] == "FORBIDDEN_WORD_DETECTED"


@pytest.mark.django_db
class TestLanternDelete:
    def test_delete_success(self, auth_client, user, booth):
        booth.lantern_count = 1
        booth.save(update_fields=["lantern_count"])
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="삭제될 등불", festival_date=FESTIVAL_DAY
        )

        response = auth_client.delete(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "LANTERN_DELETE_SUCCESS"
        assert body["data"] == {}

        lantern.refresh_from_db()
        assert lantern.deleted_at is not None
        assert lantern.deleted_by == Lantern.DeletedBy.USER

        booth.refresh_from_db()
        assert booth.lantern_count == 0

    def test_delete_allows_past_date_lantern(self, auth_client, user, booth):
        booth.lantern_count = 1
        booth.save(update_fields=["lantern_count"])
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="어제 등불", festival_date=OUT_OF_FESTIVAL_DAY
        )
        response = auth_client.delete(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 200

    def test_delete_rejects_not_owner(self, auth_client, other_user, booth):
        lantern = Lantern.objects.create(
            user=other_user, booth=booth, message="다른 사람 등불", festival_date=FESTIVAL_DAY
        )
        response = auth_client.delete(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 403
        assert response.json()["code"] == "NOT_OWNER"

    def test_delete_rejects_missing_lantern(self, auth_client):
        response = auth_client.delete("/api/lanterns/999999/")
        assert response.status_code == 404
        assert response.json()["code"] == "LANTERN_NOT_FOUND"

    def test_delete_rejects_already_deleted(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="삭제될 등불", festival_date=FESTIVAL_DAY
        )
        lantern.deleted_at = timezone.now()
        lantern.deleted_by = Lantern.DeletedBy.USER
        lantern.save()

        response = auth_client.delete(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 409
        assert response.json()["code"] == "ALREADY_DELETED"

    def test_perform_destroy_is_idempotent_under_concurrent_calls(self, user, booth):
        booth.lantern_count = 1
        booth.save(update_fields=["lantern_count"])
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="동시 삭제 테스트", festival_date=FESTIVAL_DAY
        )

        viewset = LanternViewSet()
        viewset.perform_destroy(lantern)

        with pytest.raises(ApiError) as exc_info:
            viewset.perform_destroy(lantern)

        assert exc_info.value.code == "ALREADY_DELETED"

        booth.refresh_from_db()
        assert booth.lantern_count == 0
