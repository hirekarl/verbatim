"""Tests for the Google Docs API client module."""

from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from verbatim.docs_client import (
    CampaignContext,
    DocsClientError,
    DocumentAccessDeniedError,
    DocumentContent,
    DocumentNotFoundError,
    GoogleDocsClient,
    Heading,
    _extract_title_body_and_headings,
    _fetch_document,
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
