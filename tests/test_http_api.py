"""Tests for the Verbatim HTTP entrypoint."""

from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from verbatim.agent import AgentRunResult
from verbatim.docs_client import AuthenticationError, DocsClientError
from verbatim.http_api import app
from verbatim.llm_client import LLMClientError
from verbatim.token_validator import TokenValidationError


class TestAuditEndpoint:
    """Tests for the POST /audit HTTP entrypoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """A FastAPI test client for the audit API."""
        return TestClient(app)

    @pytest.fixture
    def mock_run_agent(self, mocker: MockerFixture) -> MagicMock:
        """Mock the run_agent function."""
        return mocker.patch("verbatim.http_api.run_agent")

    @pytest.fixture
    def mock_docs_client(self, mocker: MockerFixture) -> MagicMock:
        """Mock the GoogleDocsClient class and its from_access_token method."""
        mock_cls = mocker.patch("verbatim.http_api.GoogleDocsClient")
        return cast(MagicMock, mock_cls.from_access_token)

    @pytest.fixture
    def mock_llm_client(self, mocker: MockerFixture) -> MagicMock:
        """Mock the OpenRouterClient class and its from_env method."""
        mock_cls = mocker.patch("verbatim.http_api.OpenRouterClient")
        return cast(MagicMock, mock_cls.from_env)

    @pytest.fixture
    def mock_brand_guidelines(self, mocker: MockerFixture) -> MagicMock:
        """Mock the BrandGuidelines class."""
        return mocker.patch("verbatim.http_api.BrandGuidelines")

    @pytest.fixture(autouse=True)
    def mock_validate_access_token(self, mocker: MockerFixture) -> MagicMock:
        """Mock token validation so tests don't hit the real tokeninfo endpoint."""
        return mocker.patch("verbatim.http_api.validate_access_token")

    def test_audit_success(
        self,
        client: TestClient,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
    ) -> None:
        """A valid request with a bearer token runs the agent and returns JSON."""
        mock_run_agent.return_value = AgentRunResult(
            suggestions_made=3,
            comments_made=5,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )

        response = client.post(
            "/audit",
            json={
                "document_id": "doc-id",
                "brief_id": "brief-id",
                "channel": "email",
                "model": "custom/model",
            },
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "suggestions_made": 3,
            "comments_made": 5,
            "stopped_due_to_max_rounds": False,
        }
        mock_docs_client.assert_called_once_with("fake-token", include_drive=True)
        mock_llm_client.assert_called_once_with(model="custom/model")
        mock_brand_guidelines.assert_called_once_with(None)
        mock_run_agent.assert_called_once_with(
            docs_client=mock_docs_client.return_value,
            llm_client=mock_llm_client.return_value,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=mock_brand_guidelines.return_value,
            target_channel="email",
        )

    def test_audit_defaults(
        self,
        client: TestClient,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
    ) -> None:
        """Omitted optional fields fall back to CLI-matching defaults."""
        mock_run_agent.return_value = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=True,
        )

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        mock_llm_client.assert_called_once_with(model="google/gemini-2.5-flash")
        mock_run_agent.assert_called_once_with(
            docs_client=mock_docs_client.return_value,
            llm_client=mock_llm_client.return_value,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=mock_brand_guidelines.return_value,
            target_channel=None,
        )

    def test_audit_missing_authorization_header(self, client: TestClient) -> None:
        """A request with no Authorization header is rejected before the agent runs."""
        response = client.post(
            "/audit", json={"document_id": "doc-id", "brief_id": "brief-id"}
        )

        assert response.status_code == 401

    def test_audit_malformed_authorization_header(self, client: TestClient) -> None:
        """A non-Bearer Authorization header is rejected before running the agent."""
        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        assert response.status_code == 401

    def test_audit_malformed_body(self, client: TestClient) -> None:
        """A request missing required fields returns FastAPI's validation error."""
        response = client.post(
            "/audit",
            json={"document_id": "doc-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 422

    def test_audit_authentication_error(
        self,
        client: TestClient,
        mock_docs_client: MagicMock,
    ) -> None:
        """AuthenticationError from the docs client maps to 401."""
        mock_docs_client.side_effect = AuthenticationError("bad token")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "bad token"

    def test_audit_docs_client_error(
        self,
        client: TestClient,
        mock_docs_client: MagicMock,
    ) -> None:
        """A generic DocsClientError maps to 502."""
        mock_docs_client.side_effect = DocsClientError("upstream failure")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 502

    def test_audit_llm_client_error(
        self,
        client: TestClient,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """An LLMClientError maps to 502."""
        mock_llm_client.side_effect = LLMClientError("api key missing")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 502

    def test_audit_value_error(
        self,
        client: TestClient,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
        mock_run_agent: MagicMock,
    ) -> None:
        """A ValueError raised during the run maps to 400."""
        mock_run_agent.side_effect = ValueError("bad channel")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 400

    def test_audit_unexpected_error(
        self,
        client: TestClient,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Unexpected exceptions map to 500."""
        mock_llm_client.side_effect = RuntimeError("boom")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 500

    def test_audit_token_validation_error(
        self,
        client: TestClient,
        mock_validate_access_token: MagicMock,
        mock_docs_client: MagicMock,
    ) -> None:
        """A token that fails tokeninfo validation maps to 401, before any API call."""
        mock_validate_access_token.side_effect = TokenValidationError("bad audience")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "bad audience"
        mock_docs_client.assert_not_called()

    def test_audit_token_validation_unreachable(
        self,
        client: TestClient,
        mock_validate_access_token: MagicMock,
    ) -> None:
        """A tokeninfo network failure maps to 502, not 401."""
        mock_validate_access_token.side_effect = DocsClientError("unreachable")

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 502

    def test_audit_token_validation_misconfigured(
        self,
        client: TestClient,
        mock_validate_access_token: MagicMock,
    ) -> None:
        """A missing GOOGLE_OAUTH_CLIENT_ID surfaces as a 500, not a 401."""
        mock_validate_access_token.side_effect = RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID environment variable is not set"
        )

        response = client.post(
            "/audit",
            json={"document_id": "doc-id", "brief_id": "brief-id"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 500
