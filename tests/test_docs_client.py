"""Tests for the Google Docs API client module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError
from pytest_mock import MockerFixture

from verbatim.docs_client import (
    AuthenticationError,
    CampaignContext,
    DocsClientError,
    DocumentAccessDeniedError,
    DocumentContent,
    DocumentNotFoundError,
    GoogleDocsClient,
    Heading,
    _extract_title_body_and_headings,
    _fetch_document,
    _load_credentials,
)

_FAKE_DOCUMENT_JSON = {
    "title": "Q3 Launch Blog Draft",
    "body": {
        "content": [
            {
                "paragraph": {
                    "elements": [{"textRun": {"content": "Big News!\n"}}],
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                }
            },
            {
                "paragraph": {
                    "elements": [
                        {"textRun": {"content": "Our new feature helps you.\n"}}
                    ],
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                }
            },
        ]
    },
}


def _make_http_error(status: int) -> HttpError:
    """Build an HttpError with the given status code, as raised by googleapiclient."""
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"{}")


class TestExtractTitleBodyAndHeadings:
    """Tests for the pure Docs API JSON parsing helper."""

    def test_concatenates_text_runs_across_paragraphs_into_body_text(self) -> None:
        """Body text is the concatenation of every paragraph's text runs."""
        document = {
            "title": "Q3 Launch Blog Draft",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Big News!\n"}}],
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Our new feature helps "}},
                                {"textRun": {"content": "you move faster.\n"}},
                            ],
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        }
                    },
                ]
            },
        }

        title, body_text, _headings = _extract_title_body_and_headings(document)

        assert title == "Q3 Launch Blog Draft"
        assert body_text == "Big News!\nOur new feature helps you move faster.\n"

    def test_collects_headings_with_correct_levels_in_document_order(self) -> None:
        """Headings are collected in document order with their heading level."""
        document = {
            "title": "Doc",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Intro\n"}}],
                            "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Body copy.\n"}}],
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Details\n"}}],
                            "paragraphStyle": {"namedStyleType": "HEADING_2"},
                        }
                    },
                ]
            },
        }

        _title, _body_text, headings = _extract_title_body_and_headings(document)

        assert headings == [
            Heading(level=1, text="Intro\n"),
            Heading(level=2, text="Details\n"),
        ]

    def test_returns_empty_headings_list_when_document_has_no_headings(self) -> None:
        """A document with only normal-text paragraphs has no headings."""
        document = {
            "title": "Doc",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Just text.\n"}}],
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        }
                    },
                ]
            },
        }

        _title, _body_text, headings = _extract_title_body_and_headings(document)

        assert headings == []

    def test_skips_structural_elements_without_a_paragraph(self) -> None:
        """Non-paragraph structural elements (e.g. section breaks) are skipped."""
        document = {
            "title": "Doc",
            "body": {
                "content": [
                    {"sectionBreak": {}},
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "After break.\n"}}],
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        }
                    },
                ]
            },
        }

        _title, body_text, _headings = _extract_title_body_and_headings(document)

        assert body_text == "After break.\n"


class TestFetchDocument:
    """Tests for the HTTP-error-mapping document fetch helper."""

    def test_returns_the_document_json_on_success(self) -> None:
        """A successful call returns the document JSON payload unchanged."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = {
            "title": "Doc"
        }

        document = _fetch_document(service, "doc-id")

        assert document == {"title": "Doc"}
        service.documents.return_value.get.assert_called_once_with(documentId="doc-id")

    def test_raises_document_not_found_error_on_http_404(self) -> None:
        """A 404 HttpError is mapped to DocumentNotFoundError."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.side_effect = (
            _make_http_error(404)
        )

        with pytest.raises(DocumentNotFoundError):
            _fetch_document(service, "doc-id")

    def test_raises_document_access_denied_error_on_http_403(self) -> None:
        """A 403 HttpError is mapped to DocumentAccessDeniedError."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.side_effect = (
            _make_http_error(403)
        )

        with pytest.raises(DocumentAccessDeniedError):
            _fetch_document(service, "doc-id")

    def test_wraps_unexpected_http_errors_as_docs_client_error(self) -> None:
        """Any other HttpError is wrapped as the generic DocsClientError."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.side_effect = (
            _make_http_error(500)
        )

        with pytest.raises(DocsClientError):
            _fetch_document(service, "doc-id")


class TestGoogleDocsClientGetDocumentContent:
    """Tests for GoogleDocsClient.get_document_content."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_JSON
        )
        return service

    @pytest.fixture
    def client(self, fake_service: MagicMock) -> GoogleDocsClient:
        """A GoogleDocsClient wired to the fake service."""
        return GoogleDocsClient(service=fake_service)

    def test_returns_document_content_with_title_body_and_headings(
        self, client: GoogleDocsClient
    ) -> None:
        """The parsed document is returned as a DocumentContent."""
        content = client.get_document_content("doc-id")

        assert content == DocumentContent(
            document_id="doc-id",
            title="Q3 Launch Blog Draft",
            body_text="Big News!\nOur new feature helps you.\n",
            headings=[Heading(level=1, text="Big News!\n")],
        )

    def test_calls_documents_get_with_the_given_document_id(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """The document ID passed in is forwarded to the underlying API call."""
        client.get_document_content("doc-id")

        fake_service.documents.return_value.get.assert_called_once_with(
            documentId="doc-id"
        )

    def test_raises_document_not_found_error_on_http_404(
        self, fake_service: MagicMock
    ) -> None:
        """A 404 from the underlying API surfaces as DocumentNotFoundError."""
        fake_service.documents.return_value.get.return_value.execute.side_effect = (
            _make_http_error(404)
        )
        client = GoogleDocsClient(service=fake_service)

        with pytest.raises(DocumentNotFoundError):
            client.get_document_content("doc-id")


class TestGoogleDocsClientGetCampaignContext:
    """Tests for GoogleDocsClient.get_campaign_context."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed brief document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_JSON
        )
        return service

    @pytest.fixture
    def client(self, fake_service: MagicMock) -> GoogleDocsClient:
        """A GoogleDocsClient wired to the fake service."""
        return GoogleDocsClient(service=fake_service)

    def test_returns_campaign_context_with_title_body_and_headings(
        self, client: GoogleDocsClient
    ) -> None:
        """The parsed brief document is returned as a CampaignContext."""
        context = client.get_campaign_context("brief-id")

        assert context == CampaignContext(
            document_id="brief-id",
            title="Q3 Launch Blog Draft",
            body_text="Big News!\nOur new feature helps you.\n",
            headings=[Heading(level=1, text="Big News!\n")],
        )

    def test_calls_documents_get_with_the_given_brief_id(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """The brief document ID passed in is forwarded to the underlying API call."""
        client.get_campaign_context("brief-id")

        fake_service.documents.return_value.get.assert_called_once_with(
            documentId="brief-id"
        )


class TestLoadCredentials:
    """Tests for OAuth credential loading, refresh, and consent-flow branches."""

    def test_loads_cached_valid_token_without_running_consent_flow(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """A cached valid token is returned as-is; no consent flow runs."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")
        client_secret_path = tmp_path / "client_secret.json"
        fake_creds = MagicMock(valid=True)
        mock_credentials = mocker.patch("verbatim.docs_client.Credentials")
        mock_credentials.from_authorized_user_file.return_value = fake_creds
        mock_flow = mocker.patch("verbatim.docs_client.InstalledAppFlow")

        result = _load_credentials(client_secret_path, token_path, ["scope"])

        assert result is fake_creds
        mock_flow.from_client_secrets_file.assert_not_called()

    def test_refreshes_an_expired_token_using_its_refresh_token(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """An expired cached token with a refresh token is refreshed and persisted."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")
        client_secret_path = tmp_path / "client_secret.json"
        fake_creds = MagicMock(valid=False, expired=True, refresh_token="refresh-me")
        fake_creds.to_json.return_value = '{"refreshed": true}'
        mock_credentials = mocker.patch("verbatim.docs_client.Credentials")
        mock_credentials.from_authorized_user_file.return_value = fake_creds
        mock_request = mocker.patch("verbatim.docs_client.Request")
        mock_flow = mocker.patch("verbatim.docs_client.InstalledAppFlow")

        result = _load_credentials(client_secret_path, token_path, ["scope"])

        assert result is fake_creds
        fake_creds.refresh.assert_called_once_with(mock_request.return_value)
        mock_flow.from_client_secrets_file.assert_not_called()
        assert token_path.read_text() == '{"refreshed": true}'

    def test_runs_local_server_consent_flow_when_no_cached_token_exists(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """With no cached token, the installed-app consent flow runs and persists."""
        token_path = tmp_path / "token.json"
        client_secret_path = tmp_path / "client_secret.json"
        client_secret_path.write_text("{}")
        fake_creds = MagicMock()
        fake_creds.to_json.return_value = '{"new": true}'
        mock_flow_class = mocker.patch("verbatim.docs_client.InstalledAppFlow")
        mock_run_local_server = (
            mock_flow_class.from_client_secrets_file.return_value.run_local_server
        )
        mock_run_local_server.return_value = fake_creds
        mock_credentials = mocker.patch("verbatim.docs_client.Credentials")

        result = _load_credentials(client_secret_path, token_path, ["scope"])

        assert result is fake_creds
        mock_credentials.from_authorized_user_file.assert_not_called()
        mock_flow_class.from_client_secrets_file.assert_called_once_with(
            str(client_secret_path), ["scope"]
        )
        assert token_path.read_text() == '{"new": true}'

    def test_raises_authentication_error_when_client_secret_file_is_missing(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Missing client secret file with no cached token raises an error."""
        token_path = tmp_path / "token.json"
        client_secret_path = tmp_path / "client_secret.json"
        mock_flow = mocker.patch("verbatim.docs_client.InstalledAppFlow")

        with pytest.raises(AuthenticationError):
            _load_credentials(client_secret_path, token_path, ["scope"])

        mock_flow.from_client_secrets_file.assert_not_called()

    def test_raises_authentication_error_when_refresh_fails(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """A refresh failure on an expired cached token raises AuthenticationError."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")
        client_secret_path = tmp_path / "client_secret.json"
        fake_creds = MagicMock(valid=False, expired=True, refresh_token="refresh-me")
        fake_creds.refresh.side_effect = Exception("network error")
        mock_credentials = mocker.patch("verbatim.docs_client.Credentials")
        mock_credentials.from_authorized_user_file.return_value = fake_creds
        mocker.patch("verbatim.docs_client.Request")

        with pytest.raises(AuthenticationError):
            _load_credentials(client_secret_path, token_path, ["scope"])

    def test_raises_authentication_error_when_consent_flow_fails(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """A failure during the installed-app consent flow raises an error."""
        token_path = tmp_path / "token.json"
        client_secret_path = tmp_path / "client_secret.json"
        client_secret_path.write_text("{}")
        mock_flow_class = mocker.patch("verbatim.docs_client.InstalledAppFlow")
        mock_run_local_server = (
            mock_flow_class.from_client_secrets_file.return_value.run_local_server
        )
        mock_run_local_server.side_effect = Exception("consent denied")
        mocker.patch("verbatim.docs_client.Credentials")

        with pytest.raises(AuthenticationError):
            _load_credentials(client_secret_path, token_path, ["scope"])


class TestGoogleDocsClientFromLocalCredentials:
    """Tests that from_local_credentials wires loaded credentials into build()."""

    def test_builds_docs_v1_service_with_the_loaded_credentials(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """from_local_credentials loads credentials and builds the docs v1 service."""
        fake_creds = MagicMock()
        fake_service = MagicMock()
        mock_load_credentials = mocker.patch(
            "verbatim.docs_client._load_credentials", return_value=fake_creds
        )
        mock_build = mocker.patch(
            "verbatim.docs_client.build", return_value=fake_service
        )
        client_secret_path = tmp_path / "client_secret.json"
        token_path = tmp_path / "token.json"

        client = GoogleDocsClient.from_local_credentials(
            client_secret_path=client_secret_path, token_path=token_path
        )

        mock_load_credentials.assert_called_once_with(
            client_secret_path,
            token_path,
            ["https://www.googleapis.com/auth/documents.readonly"],
        )
        mock_build.assert_called_once_with("docs", "v1", credentials=fake_creds)
        assert client._service is fake_service
