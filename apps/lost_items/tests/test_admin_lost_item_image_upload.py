"""관리자 분실물 이미지 업로드 API 테스트."""

import io
from urllib.parse import urlparse

import pytest
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


pytestmark = pytest.mark.django_db

UPLOAD_URL = "/api/admin/lost-items/images/"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """테스트용 임시 미디어 경로를 설정한다."""

    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def make_image(fmt="PNG", name="sample.png", size=(20, 20)):
    """테스트용 이미지 파일을 생성한다."""

    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    buffer.seek(0)

    return SimpleUploadedFile(
        name,
        buffer.read(),
        content_type=f"image/{fmt.lower()}",
    )


def get_storage_path(image_url):
    """응답 URL에서 스토리지 상대 경로를 추출한다."""

    url_path = urlparse(image_url).path
    media_prefix = f"/{settings.MEDIA_URL.strip('/')}/"

    assert url_path.startswith(media_prefix)

    return url_path.removeprefix(media_prefix)


class TestImageUpload:
    def test_uploads_png(self, client, auth_headers):
        response = client.post(
            UPLOAD_URL,
            {"file": make_image()},
            **auth_headers,
        )

        body = response.json()

        assert response.status_code == 201
        assert body["code"] == "LOST_ITEM_IMAGE_UPLOAD_SUCCESS"
        assert body["data"]["image_url"].startswith("http")
        assert body["data"]["image_url"].endswith(".png")

    def test_uploads_jpeg_and_normalizes_extension_to_jpg(
        self,
        client,
        auth_headers,
    ):
        image = make_image(
            fmt="JPEG",
            name="photo.jpeg",
        )

        response = client.post(
            UPLOAD_URL,
            {"file": image},
            **auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["data"]["image_url"].endswith(".jpg")

    def test_uploads_webp(self, client, auth_headers):
        image = make_image(
            fmt="WEBP",
            name="photo.webp",
        )

        response = client.post(
            UPLOAD_URL,
            {"file": image},
            **auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["data"]["image_url"].endswith(".webp")

    def test_saved_file_exists(self, client, auth_headers):
        response = client.post(
            UPLOAD_URL,
            {"file": make_image()},
            **auth_headers,
        )

        image_url = response.json()["data"]["image_url"]
        storage_path = get_storage_path(image_url)

        assert default_storage.exists(storage_path)

    def test_filename_is_randomized(self, client, auth_headers):
        """같은 파일명을 업로드해도 서로 다른 파일로 저장된다."""

        first = client.post(
            UPLOAD_URL,
            {"file": make_image()},
            **auth_headers,
        )
        second = client.post(
            UPLOAD_URL,
            {"file": make_image()},
            **auth_headers,
        )

        assert first.json()["data"]["image_url"] != second.json()["data"]["image_url"]

    def test_requires_auth(self, client):
        response = client.post(
            UPLOAD_URL,
            {"file": make_image()},
        )

        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"

    def test_missing_file_returns_400(self, client, auth_headers):
        response = client.post(
            UPLOAD_URL,
            {},
            **auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_INPUT"
        assert "file" in response.json()["errors"]

    def test_unsupported_extension_returns_415(
        self,
        client,
        auth_headers,
    ):
        gif = SimpleUploadedFile(
            "sample.gif",
            b"GIF89a",
            content_type="image/gif",
        )

        response = client.post(
            UPLOAD_URL,
            {"file": gif},
            **auth_headers,
        )

        assert response.status_code == 415
        assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_renamed_non_image_returns_415(
        self,
        client,
        auth_headers,
    ):
        """확장자만 이미지로 변경한 파일은 거부한다."""

        fake = SimpleUploadedFile(
            "fake.png",
            b"not-an-image",
            content_type="image/png",
        )

        response = client.post(
            UPLOAD_URL,
            {"file": fake},
            **auth_headers,
        )

        assert response.status_code == 415
        assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_extension_and_actual_format_mismatch_returns_415(
        self,
        client,
        auth_headers,
    ):
        """파일 확장자와 실제 이미지 포맷이 다르면 거부한다."""

        image = make_image(
            fmt="JPEG",
            name="fake.png",
        )

        response = client.post(
            UPLOAD_URL,
            {"file": image},
            **auth_headers,
        )

        assert response.status_code == 415
        assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_oversized_file_returns_413(
        self,
        client,
        auth_headers,
        settings,
    ):
        settings.LOST_ITEM_IMAGE_MAX_BYTES = 100

        image = make_image(size=(200, 200))

        assert image.size > settings.LOST_ITEM_IMAGE_MAX_BYTES

        response = client.post(
            UPLOAD_URL,
            {"file": image},
            **auth_headers,
        )

        assert response.status_code == 413
        assert response.json()["code"] == "FILE_TOO_LARGE"