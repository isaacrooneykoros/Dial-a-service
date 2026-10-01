"""Uploads to private storage (M1 T08, ADR-0004)."""

from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
import time_machine
from botocore.stub import Stubber
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tests.helpers import client_for, sign_in
from apps.core.models import Upload
from apps.core.storage import LocalStorage, R2Storage
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import assert_cross_business_404
from apps.core.tests.factories import UploadFactory
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

START = "/api/v1/uploads"
PHOTO = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


@pytest.fixture(autouse=True)
def private_root(settings: Any, tmp_path: Path) -> Path:
    settings.MEDIA_PRIVATE_ROOT = tmp_path
    settings.STORAGE_BACKEND = "local"
    return tmp_path


@pytest.fixture
def staff(business_a: Business) -> User:
    with tenant_context(business_a.id):
        user: User = UserFactory()
    return user


def app(business: Business, user: User) -> Any:
    return client_for(business, sign_in(user).access)


def start(client: Any, content_type: str = "image/jpeg", size: int = len(PHOTO)) -> Any:
    return client.post(START, {"content_type": content_type, "size": size}, format="json")


def put(client: Any, url: str, body: bytes = PHOTO, content_type: str = "image/jpeg") -> Any:
    return client.generic("PUT", url, body, content_type=content_type)


class TestStart:
    def test_returns_a_short_lived_url_and_a_business_prefixed_key(
        self, business_a: Business, staff: User
    ) -> None:
        response = start(app(business_a, staff))
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["method"] == "PUT"
        assert body["headers"] == {"Content-Type": "image/jpeg"}
        assert body["url"].startswith(f"/api/v1/uploads/{body['upload_id']}/content?token=")
        with tenant_context(business_a.id):
            upload = Upload.objects.get()
        assert upload.key == f"{business_a.id}/uploads/{upload.pk}.jpg"
        assert upload.status == Upload.Status.PENDING
        assert upload.uploaded_by_id == staff.pk

    @pytest.mark.parametrize(
        ("content_type", "size", "code"),
        [
            ("application/pdf", 10, "unsupported_type"),
            ("image/gif", 10, "unsupported_type"),
            ("image/jpeg", 5 * 1024 * 1024 + 1, "too_large"),
        ],
    )
    def test_limits(
        self, business_a: Business, staff: User, content_type: str, size: int, code: str
    ) -> None:
        response = start(app(business_a, staff), content_type, size)
        assert response.status_code == 400
        assert response.json()["code"] == code

    def test_size_must_be_positive(self, business_a: Business, staff: User) -> None:
        response = start(app(business_a, staff), size=0)
        assert response.status_code == 400
        assert "size" in response.json()["fields"]

    def test_needs_sign_in(self, business_a: Business) -> None:
        assert client_for(business_a).post(START, {}, format="json").status_code == 401


class TestLocalFlow:
    def test_put_then_complete(self, business_a: Business, staff: User) -> None:
        client = app(business_a, staff)
        ticket = start(client).json()
        assert put(client_for(business_a), ticket["url"]).status_code == 200
        done = client.post(f"/api/v1/uploads/{ticket['upload_id']}/complete")
        assert done.status_code == 200
        assert done.json()["status"] == "uploaded"
        again = client.post(f"/api/v1/uploads/{ticket['upload_id']}/complete")
        assert again.json()["status"] == "uploaded"

    def test_complete_before_the_file_arrives(self, business_a: Business, staff: User) -> None:
        client = app(business_a, staff)
        ticket = start(client).json()
        response = client.post(f"/api/v1/uploads/{ticket['upload_id']}/complete")
        assert response.status_code == 409
        assert response.json()["code"] == "not_uploaded"

    def test_a_smaller_file_than_declared_does_not_complete(
        self, business_a: Business, staff: User
    ) -> None:
        client = app(business_a, staff)
        ticket = start(client).json()
        put(client_for(business_a), ticket["url"], body=PHOTO[:5])
        response = client.post(f"/api/v1/uploads/{ticket['upload_id']}/complete")
        assert response.json()["code"] == "does_not_match"

    def test_wrong_type_or_too_many_bytes_are_refused(
        self, business_a: Business, staff: User
    ) -> None:
        ticket = start(app(business_a, staff)).json()
        public = client_for(business_a)
        assert put(public, ticket["url"], content_type="image/png").status_code == 400
        assert put(public, ticket["url"], body=PHOTO + b"extra").status_code == 400

    def test_expired_links(self, business_a: Business, staff: User) -> None:
        ticket = start(app(business_a, staff)).json()
        with time_machine.travel(timezone.now() + timedelta(minutes=6)):
            assert put(client_for(business_a), ticket["url"]).status_code == 404

    def test_tampered_links(self, business_a: Business, staff: User) -> None:
        ticket = start(app(business_a, staff)).json()
        assert put(client_for(business_a), ticket["url"] + "x").status_code == 404
        other = start(app(business_a, staff)).json()
        token = parse_qs(urlparse(ticket["url"]).query)["token"][0]
        swapped = f"/api/v1/uploads/{other['upload_id']}/content?token={token}"
        assert put(client_for(business_a), swapped).status_code == 404

    def test_a_link_is_useless_on_another_business_host(
        self, business_a: Business, business_b: Business, staff: User
    ) -> None:
        ticket = start(app(business_a, staff)).json()
        assert put(client_for(business_b), ticket["url"]).status_code == 404

    def test_only_put(self, business_a: Business, staff: User) -> None:
        ticket = start(app(business_a, staff)).json()
        assert client_for(business_a).get(ticket["url"]).status_code == 404

    def test_files_stay_inside_the_private_folder(self, private_root: Path) -> None:
        with pytest.raises(ValueError, match="escapes"):
            LocalStorage().path_for("../outside.jpg")
        assert LocalStorage().stat("nothing/here.jpg") is None


class TestR2Adapter:
    @pytest.fixture
    def r2(self, settings: Any) -> R2Storage:
        settings.STORAGE_ENDPOINT = "https://account.r2.cloudflarestorage.com"
        settings.STORAGE_BUCKET = "dial-a-service"
        settings.STORAGE_ACCESS_KEY = "access"
        settings.STORAGE_SECRET_KEY = "secret"
        return R2Storage()

    def test_presigned_put_url(self, r2: R2Storage) -> None:
        url = r2.upload_url(
            key="b1/uploads/u1.jpg", content_type="image/jpeg", upload_id="u1", business_id="b1"
        )
        parsed = urlparse(url)
        assert parsed.netloc == "account.r2.cloudflarestorage.com"
        assert parsed.path == "/dial-a-service/b1/uploads/u1.jpg"
        assert parse_qs(parsed.query)["X-Amz-Expires"] == ["300"]

    def test_stat(self, r2: R2Storage) -> None:
        with Stubber(r2.client) as stub:
            stub.add_response(
                "head_object",
                {"ContentLength": 12, "ContentType": "image/jpeg"},
                {"Bucket": "dial-a-service", "Key": "k.jpg"},
            )
            stub.add_client_error("head_object", "404", http_status_code=404)
            found = r2.stat("k.jpg")
            missing = r2.stat("gone.jpg")
        assert found is not None
        assert (found.size, found.content_type) == (12, "image/jpeg")
        assert missing is None

    def test_r2_is_used_when_configured(self, settings: Any, r2: R2Storage) -> None:
        from apps.core.storage import get_storage

        settings.STORAGE_BACKEND = "r2"
        assert isinstance(get_storage(), R2Storage)


def test_cross_business(business_a: Business, business_b: Business) -> None:
    with tenant_context(business_b.id):
        their_user = UserFactory()
    with tenant_context(business_a.id):
        our_user = UserFactory()

    def make() -> Upload:
        upload: Upload = UploadFactory(status=Upload.Status.UPLOADED)
        return upload

    assert_cross_business_404(
        owner=business_b,
        owner_client=app(business_b, their_user),
        intruder=app(business_a, our_user),
        make_object=make,
        url_for=lambda upload: f"/api/v1/uploads/{upload.pk}/complete",
        method="post",
    )
