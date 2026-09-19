import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

IMAGE_UPLOAD_URL = "/api/notices/images/"


def _create_test_image(format_type="JPEG") -> io.BytesIO:
    """테스트용 인메모리 유효 이미지 바이트를 생성합니다."""
    image = Image.new("RGB", (100, 100), color="blue")
    byte_io = io.BytesIO()
    image.save(byte_io, format=format_type)
    byte_io.seek(0)
    return byte_io


@pytest.mark.django_db
class TestAdminNoticeImageUploadAPI:
    def test_unauthorized_access_denied(self, client):
        img_io = _create_test_image("JPEG")
        upload_file = SimpleUploadedFile("test.jpg", img_io.getvalue(), content_type="image/jpeg")

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file})
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "UNAUTHORIZED"

    def test_upload_image_success_jpg(self, client, auth_headers):
        img_io = _create_test_image("JPEG")
        upload_file = SimpleUploadedFile("photo.jpg", img_io.getvalue(), content_type="image/jpeg")

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file}, **auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "IMAGE_UPLOAD_SUCCESS"
        assert "image_url" in data["data"]
        assert data["data"]["image_url"].endswith(".jpg")

    def test_upload_image_success_png(self, client, auth_headers):
        img_io = _create_test_image("PNG")
        upload_file = SimpleUploadedFile("photo.png", img_io.getvalue(), content_type="image/png")

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file}, **auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "IMAGE_UPLOAD_SUCCESS"
        assert data["data"]["image_url"].endswith(".png")

    def test_upload_image_success_webp(self, client, auth_headers):
        img_io = _create_test_image("WEBP")
        upload_file = SimpleUploadedFile("photo.webp", img_io.getvalue(), content_type="image/webp")

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file}, **auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "IMAGE_UPLOAD_SUCCESS"
        assert data["data"]["image_url"].endswith(".webp")

    def test_upload_image_missing_file_fails(self, client, auth_headers):
        response = client.post(IMAGE_UPLOAD_URL, data={}, **auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_IMAGE_FILE"
        assert "image" in data["errors"]

    def test_upload_image_invalid_content_type_fails(self, client, auth_headers):
        img_io = _create_test_image("JPEG")
        upload_file = SimpleUploadedFile(
            "photo.jpg", img_io.getvalue(), content_type="application/octet-stream"
        )

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file}, **auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_IMAGE_FILE"
        assert "image" in data["errors"]

    def test_upload_image_invalid_extension_fails(self, client, auth_headers):
        upload_file = SimpleUploadedFile(
            "doc.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"
        )

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file}, **auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_IMAGE_FILE"
        assert "image" in data["errors"]

    def test_upload_image_corrupted_image_fails(self, client, auth_headers):
        upload_file = SimpleUploadedFile(
            "fake.jpg", b"not-a-valid-image-content", content_type="image/jpeg"
        )

        response = client.post(IMAGE_UPLOAD_URL, data={"image": upload_file}, **auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_IMAGE_FILE"

    def test_upload_image_file_size_exceeded_fails(self, client, auth_headers):
        # 10MB + 100 bytes
        large_size = 10 * 1024 * 1024 + 100
        large_file = SimpleUploadedFile(
            "huge.jpg", b"0" * large_size, content_type="image/jpeg"
        )

        response = client.post(IMAGE_UPLOAD_URL, data={"image": large_file}, **auth_headers)
        assert response.status_code == 413
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "FILE_SIZE_EXCEEDED"
        assert "10MB" in data["message"]
