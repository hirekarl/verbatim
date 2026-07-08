"""Tests for the inbound bearer-token validation module."""

from unittest.mock import MagicMock

import httpx
import pytest
from pytest_mock import MockerFixture

from verbatim.docs_client import DocsClientError
from verbatim.token_validator import TokenValidationError, validate_access_token


def _fake_tokeninfo_response(
    status_code: int = 200,
    aud: str | None = "expected-client-id",
    azp: str | None = None,
    scope: str = "https://www.googleapis.com/auth/documents",
) -> MagicMock:
    """Build a fake httpx.Response-shaped mock for the tokeninfo endpoint."""
    payload: dict[str, str] = {"scope": scope}
    if aud is not None:
        payload["aud"] = aud
    if azp is not None:
        payload["azp"] = azp
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


class TestValidateAccessToken:
    """Tests for validate_access_token."""

    @pytest.fixture(autouse=True)
    def _mock_load_dotenv(self, mocker: MockerFixture) -> None:
        """Prevent a real .env file on disk from affecting these tests."""
        mocker.patch("verbatim.token_validator.load_dotenv")

    @pytest.fixture(autouse=True)
    def _set_client_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Configure the expected OAuth client ID for these tests."""
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "expected-client-id")

    def test_raises_runtime_error_when_client_id_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no GOOGLE_OAUTH_CLIENT_ID configured, validation can't proceed."""
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)

        with pytest.raises(RuntimeError):
            validate_access_token("some-token")

    def test_raises_docs_client_error_on_network_failure(
        self, mocker: MockerFixture
    ) -> None:
        """A tokeninfo network failure is a backend problem, not an invalid token."""
        mocker.patch(
            "verbatim.token_validator.httpx.get",
            side_effect=httpx.ConnectError("connection refused"),
        )

        with pytest.raises(DocsClientError):
            validate_access_token("some-token")

    def test_raises_token_validation_error_on_non_200_response(
        self, mocker: MockerFixture
    ) -> None:
        """A non-200 tokeninfo response means the token is invalid/expired."""
        mocker.patch(
            "verbatim.token_validator.httpx.get",
            return_value=_fake_tokeninfo_response(status_code=400),
        )

        with pytest.raises(TokenValidationError):
            validate_access_token("some-token")

    def test_raises_token_validation_error_on_audience_mismatch(
        self, mocker: MockerFixture
    ) -> None:
        """A token minted for a different OAuth client is rejected."""
        mocker.patch(
            "verbatim.token_validator.httpx.get",
            return_value=_fake_tokeninfo_response(aud="someone-elses-client-id"),
        )

        with pytest.raises(TokenValidationError):
            validate_access_token("some-token")

    def test_falls_back_to_azp_when_aud_is_absent(self, mocker: MockerFixture) -> None:
        """When aud is missing, azp is checked instead."""
        mocker.patch(
            "verbatim.token_validator.httpx.get",
            return_value=_fake_tokeninfo_response(aud=None, azp="expected-client-id"),
        )

        validate_access_token("some-token")

    def test_raises_token_validation_error_on_missing_scope(
        self, mocker: MockerFixture
    ) -> None:
        """A token that doesn't carry the scope this backend needs is rejected."""
        mocker.patch(
            "verbatim.token_validator.httpx.get",
            return_value=_fake_tokeninfo_response(
                scope="https://www.googleapis.com/auth/drive.readonly"
            ),
        )

        with pytest.raises(TokenValidationError):
            validate_access_token("some-token")

    def test_succeeds_with_a_valid_token(self, mocker: MockerFixture) -> None:
        """A token with matching audience and required scope passes validation."""
        mocker.patch(
            "verbatim.token_validator.httpx.get",
            return_value=_fake_tokeninfo_response(),
        )

        validate_access_token("some-token")
