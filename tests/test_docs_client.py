"""Tests for the Google Docs API client module."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError
from pytest_mock import MockerFixture

from verbatim.docs_client import (
    AmbiguousMatchError,
    AuthenticationError,
    CampaignContext,
    DocsClientError,
    DocumentAccessDeniedError,
    DocumentContent,
    DocumentNotFoundError,
    GoogleDocsClient,
    Heading,
    SpanAlreadyEditedError,
    TextNotFoundError,
    _extract_text_chunks,
    _extract_title_body_and_headings,
    _fetch_document,
    _load_credentials,
    _locate_document_range,
    _TextChunk,
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


class TestExtractTextChunks:
    """Tests for the pure paragraph-chunk extraction helper used for range lookup."""

    def test_extracts_one_chunk_per_paragraph_with_its_start_index(self) -> None:
        """Each paragraph becomes a chunk carrying its structural startIndex."""
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Big News!\n"}}],
                        },
                    },
                    {
                        "startIndex": 11,
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Our new feature helps "}},
                                {"textRun": {"content": "you.\n"}},
                            ],
                        },
                    },
                ]
            }
        }

        chunks = _extract_text_chunks(document)

        assert chunks == [
            _TextChunk(start_index=1, text="Big News!\n", index_map=list(range(1, 11))),
            _TextChunk(
                start_index=11,
                text="Our new feature helps you.\n",
                index_map=list(range(11, 38)),
            ),
        ]

    def test_skips_structural_elements_without_a_paragraph(self) -> None:
        """Non-paragraph structural elements (e.g. section breaks) are skipped."""
        document = {
            "body": {
                "content": [
                    {"startIndex": 1, "sectionBreak": {}},
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "After break.\n"}}],
                        },
                    },
                ]
            }
        }

        chunks = _extract_text_chunks(document)

        assert chunks == [
            _TextChunk(
                start_index=1,
                text="After break.\n",
                index_map=list(range(1, 14)),
            )
        ]


class TestLocateDocumentRange:
    """Tests for locating a unique UTF-16 [start, end) range of matched text."""

    def test_finds_the_range_of_a_unique_match(self) -> None:
        """A unique match returns its start/end index within its paragraph."""
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Big News!\n"}}],
                        },
                    },
                ]
            }
        }

        start, end = _locate_document_range(document, "News")

        assert (start, end) == (1 + 4, 1 + 8)

    def test_raises_text_not_found_error_when_text_is_absent(self) -> None:
        """No occurrences anywhere in the document raises TextNotFoundError."""
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Big News!\n"}}],
                        },
                    },
                ]
            }
        }

        with pytest.raises(TextNotFoundError):
            _locate_document_range(document, "Nowhere")

    def test_raises_ambiguous_match_error_for_a_repeated_match_within_one_paragraph(
        self,
    ) -> None:
        """A match repeated within a single paragraph raises AmbiguousMatchError."""
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "great, great news\n"}}
                            ],
                        },
                    },
                ]
            }
        }

        with pytest.raises(AmbiguousMatchError):
            _locate_document_range(document, "great")

    def test_raises_ambiguous_match_error_for_matches_across_paragraphs(self) -> None:
        """A match repeated across separate paragraphs raises AmbiguousMatchError."""
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Big news!\n"}}],
                        },
                    },
                    {
                        "startIndex": 11,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "More news.\n"}}],
                        },
                    },
                ]
            }
        }

        with pytest.raises(AmbiguousMatchError):
            _locate_document_range(document, "news")

    def test_accounts_for_surrogate_pairs_preceding_the_match(self) -> None:
        """UTF-16 surrogate pairs (e.g. emoji) before the match shift the index."""
        # U+1F389 PARTY POPPER is a surrogate pair: 2 UTF-16 code units, 1 Python char.
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 1,
                        "paragraph": {
                            "elements": [{"textRun": {"content": "\U0001f389 News\n"}}],
                        },
                    },
                ]
            }
        }

        start, end = _locate_document_range(document, "News")

        # "\U0001f389" is 2 UTF-16 units, then a space (1 unit) before "News".
        assert (start, end) == (1 + 3, 1 + 7)


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


_FAKE_DOCUMENT_WITH_INDICES = {
    "title": "Q3 Launch Blog Draft",
    "body": {
        "content": [
            {
                "startIndex": 1,
                "paragraph": {
                    "elements": [{"textRun": {"content": "Big News!\n"}}],
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                },
            },
            {
                "startIndex": 11,
                "paragraph": {
                    "elements": [
                        {"textRun": {"content": "Our new feature helps you.\n"}}
                    ],
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                },
            },
        ]
    },
}


class TestGoogleDocsClientCreateSuggestion:
    """Tests for GoogleDocsClient.create_suggestion."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def client(self, fake_service: MagicMock) -> GoogleDocsClient:
        """A GoogleDocsClient wired to the fake service."""
        return GoogleDocsClient(service=fake_service)

    def test_issues_a_batch_update_with_delete_and_insert_at_the_matched_range(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """A unique match is replaced via a delete-then-insert batchUpdate."""
        client.create_suggestion("doc-id", "feature", "capability")

        fake_service.documents.return_value.batchUpdate.assert_called_once_with(
            documentId="doc-id",
            body={
                "requests": [
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": 19, "endIndex": 26}
                        }
                    },
                    {"insertText": {"location": {"index": 19}, "text": "capability"}},
                ]
            },
        )

    def test_raises_text_not_found_error_without_calling_batch_update(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """A non-existent matched_text raises before any write is issued."""
        with pytest.raises(TextNotFoundError):
            client.create_suggestion("doc-id", "nowhere", "replacement")

        fake_service.documents.return_value.batchUpdate.assert_not_called()

    def test_raises_ambiguous_match_error_without_calling_batch_update(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """A non-unique matched_text raises before any write is issued."""
        with pytest.raises(AmbiguousMatchError):
            client.create_suggestion("doc-id", "e", "replacement")

        fake_service.documents.return_value.batchUpdate.assert_not_called()

    def test_wraps_batch_update_http_errors_as_docs_client_error(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """An HttpError from batchUpdate is wrapped as DocsClientError."""
        batch_update = fake_service.documents.return_value.batchUpdate
        batch_update.return_value.execute.side_effect = _make_http_error(500)

        with pytest.raises(DocsClientError):
            client.create_suggestion("doc-id", "feature", "capability")

    def test_raises_document_not_found_error_when_document_does_not_exist(
        self, fake_service: MagicMock
    ) -> None:
        """A 404 fetching the document propagates as DocumentNotFoundError."""
        fake_service.documents.return_value.get.return_value.execute.side_effect = (
            _make_http_error(404)
        )
        client = GoogleDocsClient(service=fake_service)

        with pytest.raises(DocumentNotFoundError):
            client.create_suggestion("doc-id", "feature", "capability")


class TestGoogleDocsClientCreateSuggestionEditorFallback:
    """Tests for create_suggestion's editor marks when the account can't suggest."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def fake_drive_service(self) -> MagicMock:
        """A fake Drive API discovery service, defaulting to non-Editor access."""
        drive_service = MagicMock()
        drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": False}
        }
        return drive_service

    @pytest.fixture
    def client(
        self, fake_service: MagicMock, fake_drive_service: MagicMock
    ) -> GoogleDocsClient:
        """A GoogleDocsClient wired to both fake services."""
        return GoogleDocsClient(service=fake_service, drive_service=fake_drive_service)

    def test_strikes_through_and_inserts_bold_replacement_when_account_can_edit(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """An Editor-capable account gets inline strikethrough+bold marks, not a
        comment.
        """
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }

        client.create_suggestion("doc-id", "feature", "capability")

        fake_drive_service.comments.return_value.create.assert_not_called()
        fake_service.documents.return_value.batchUpdate.assert_called_once_with(
            documentId="doc-id",
            body={
                "requests": [
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": 19, "endIndex": 26},
                            "textStyle": {"strikethrough": True},
                            "fields": "strikethrough",
                        }
                    },
                    {
                        "insertText": {
                            "location": {"index": 26},
                            "text": "capability",
                        }
                    },
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": 26, "endIndex": 36},
                            "textStyle": {
                                "bold": True,
                                "strikethrough": False,
                                "foregroundColor": {
                                    "color": {
                                        "rgbColor": {
                                            "red": 0.0,
                                            "green": 0.6,
                                            "blue": 0.0,
                                        }
                                    }
                                },
                            },
                            "fields": "bold,strikethrough,foregroundColor",
                        }
                    },
                ]
            },
        )

    def test_only_strikes_through_when_replacement_text_is_empty(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """A pure-cut suggestion (no replacement) skips the insert/bold requests."""
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }

        client.create_suggestion("doc-id", "feature", "")

        fake_service.documents.return_value.batchUpdate.assert_called_once_with(
            documentId="doc-id",
            body={
                "requests": [
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": 19, "endIndex": 26},
                            "textStyle": {"strikethrough": True},
                            "fields": "strikethrough",
                        }
                    },
                ]
            },
        )

    def test_wraps_batch_update_http_errors_as_docs_client_error_in_editor_branch(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """An HttpError from the editor-branch batchUpdate is wrapped as
        DocsClientError.
        """
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }
        batch_update = fake_service.documents.return_value.batchUpdate
        batch_update.return_value.execute.side_effect = _make_http_error(500)

        with pytest.raises(DocsClientError):
            client.create_suggestion("doc-id", "feature", "capability")

    def test_uses_batch_update_when_the_account_can_only_suggest(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """A Commenter/Suggester-capable account still gets a real suggestion."""
        client.create_suggestion("doc-id", "feature", "capability")

        fake_service.documents.return_value.batchUpdate.assert_called_once()
        fake_drive_service.comments.return_value.create.assert_not_called()

    def test_checks_capabilities_for_the_correct_document(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """The capability check targets the document being suggested on."""
        client.create_suggestion("doc-id", "feature", "capability")

        fake_drive_service.files.return_value.get.assert_called_once_with(
            fileId="doc-id", fields="capabilities(canEdit)"
        )

    def test_raises_text_not_found_error_without_calling_batch_update_or_comment(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """A non-existent matched_text raises before any write is issued."""
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }

        with pytest.raises(TextNotFoundError):
            client.create_suggestion("doc-id", "nowhere", "replacement")

        fake_service.documents.return_value.batchUpdate.assert_not_called()
        fake_drive_service.comments.return_value.create.assert_not_called()


class TestGoogleDocsClientCreateInlineComment:
    """Tests for GoogleDocsClient.create_inline_comment."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def fake_drive_service(self) -> MagicMock:
        """A fake Drive API discovery service, defaulting to non-Editor access."""
        drive_service = MagicMock()
        drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": False}
        }
        return drive_service

    @pytest.fixture
    def client(
        self, fake_service: MagicMock, fake_drive_service: MagicMock
    ) -> GoogleDocsClient:
        """A GoogleDocsClient wired to both fake services."""
        return GoogleDocsClient(service=fake_service, drive_service=fake_drive_service)

    def test_creates_a_drive_comment_referencing_the_matched_text(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """A unique match results in a Drive comments.create call."""
        client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

        fake_drive_service.comments.return_value.create.assert_called_once_with(
            fileId="doc-id",
            body={"content": 'Re: "feature"\n\nConsider rephrasing.'},
            fields="id",
        )

    def test_raises_docs_client_error_when_no_drive_service_configured(
        self, fake_service: MagicMock
    ) -> None:
        """Without a Drive service, the method raises rather than silently no-op."""
        client = GoogleDocsClient(service=fake_service)

        with pytest.raises(DocsClientError):
            client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

    def test_raises_text_not_found_error_without_calling_drive(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """A non-existent matched_text raises before any comment is posted."""
        with pytest.raises(TextNotFoundError):
            client.create_inline_comment("doc-id", "nowhere", "Consider rephrasing.")

        fake_drive_service.comments.return_value.create.assert_not_called()

    def test_wraps_drive_http_errors_as_docs_client_error(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """An HttpError from comments.create is wrapped as DocsClientError."""
        create = fake_drive_service.comments.return_value.create
        create.return_value.execute.side_effect = _make_http_error(500)

        with pytest.raises(DocsClientError):
            client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

    def test_applies_a_background_highlight_when_the_account_can_edit_directly(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """An Editor-capable account also gets the matched span highlighted."""
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }

        client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

        fake_service.documents.return_value.batchUpdate.assert_called_once_with(
            documentId="doc-id",
            body={
                "requests": [
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": 19, "endIndex": 26},
                            "textStyle": {
                                "backgroundColor": {
                                    "color": {
                                        "rgbColor": {
                                            "red": 1.0,
                                            "green": 1.0,
                                            "blue": 0.0,
                                        }
                                    }
                                }
                            },
                            "fields": "backgroundColor",
                        }
                    }
                ]
            },
        )

    def test_does_not_apply_a_highlight_when_the_account_cannot_edit_directly(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
    ) -> None:
        """A Commenter/Suggester-capable account's comment is left unchanged."""
        client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

        fake_service.documents.return_value.batchUpdate.assert_not_called()

    def test_checks_capabilities_for_the_correct_document(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """The capability check targets the document being commented on."""
        client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

        fake_drive_service.files.return_value.get.assert_called_once_with(
            fileId="doc-id", fields="capabilities(canEdit)"
        )

    def test_wraps_highlight_batch_update_http_errors_as_docs_client_error(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """An HttpError from the highlight batchUpdate is wrapped as DocsClientError."""
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }
        batch_update = fake_service.documents.return_value.batchUpdate
        batch_update.return_value.execute.side_effect = _make_http_error(500)

        with pytest.raises(DocsClientError):
            client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")


class TestGoogleDocsClientStaleSpanAfterEdit:
    """Tests that a comment can't land on text another call already rewrote.

    Guards against the Phase 2 concurrency failure mode where the
    Line-Editor specialist rewrites a span while the Structural specialist
    -- reasoning from its own frozen, pre-edit view of the document -- is
    still mid-run and later tries to comment on that same span.
    """

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def fake_drive_service(self) -> MagicMock:
        """A fake Drive API discovery service, defaulting to non-Editor access."""
        drive_service = MagicMock()
        drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": False}
        }
        return drive_service

    @pytest.fixture
    def client(
        self, fake_service: MagicMock, fake_drive_service: MagicMock
    ) -> GoogleDocsClient:
        """A GoogleDocsClient wired to both fake services."""
        return GoogleDocsClient(service=fake_service, drive_service=fake_drive_service)

    def test_raises_when_commenting_on_text_another_call_already_replaced(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """An overlapping create_inline_comment call is refused, not posted stale."""
        client.create_suggestion("doc-id", "feature", "capability")

        with pytest.raises(SpanAlreadyEditedError):
            client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

        fake_drive_service.comments.return_value.create.assert_not_called()

    def test_raises_when_the_comment_span_contains_an_edited_span(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """A comment spanning a superstring of an already-edited span is also
        refused."""
        client.create_suggestion("doc-id", "feature", "capability")

        with pytest.raises(SpanAlreadyEditedError):
            client.create_inline_comment(
                "doc-id", "Our new feature helps", "Consider rephrasing."
            )

        fake_drive_service.comments.return_value.create.assert_not_called()

    def test_does_not_raise_for_a_span_unrelated_to_any_edit(
        self, client: GoogleDocsClient, fake_drive_service: MagicMock
    ) -> None:
        """An unrelated span is unaffected by another span's edit record."""
        client.create_suggestion("doc-id", "feature", "capability")

        client.create_inline_comment("doc-id", "helps you", "Consider rephrasing.")

        fake_drive_service.comments.return_value.create.assert_called_once()


class TestGoogleDocsClientConcurrentWrites:
    """Tests that GoogleDocsClient serializes concurrent writes with a lock."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def client(self, fake_service: MagicMock) -> GoogleDocsClient:
        """A GoogleDocsClient wired to the fake service."""
        return GoogleDocsClient(service=fake_service)

    def test_concurrent_create_suggestion_calls_do_not_overlap(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """Two threads writing to the same document never race inside a write call."""
        in_critical_section = threading.Event()
        overlap_detected = threading.Event()

        def instrumented_execute(*args: object, **kwargs: object) -> dict[str, object]:
            if in_critical_section.is_set():
                overlap_detected.set()
            in_critical_section.set()
            time.sleep(0.05)
            in_critical_section.clear()
            return {}

        batch_update = fake_service.documents.return_value.batchUpdate
        batch_update.return_value.execute.side_effect = instrumented_execute

        threads = [
            threading.Thread(
                target=client.create_suggestion,
                args=("doc-id", "feature", f"capability-{i}"),
            )
            for i in range(5)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()

        assert not overlap_detected.is_set()


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
        assert client._drive_service is None

    def test_also_builds_drive_v3_service_when_include_drive_is_true(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """include_drive=True builds a second Drive v3 service with the same creds."""
        fake_creds = MagicMock()
        fake_docs_service = MagicMock()
        fake_drive_service = MagicMock()
        mocker.patch("verbatim.docs_client._load_credentials", return_value=fake_creds)
        mock_build = mocker.patch(
            "verbatim.docs_client.build",
            side_effect=[fake_docs_service, fake_drive_service],
        )
        client_secret_path = tmp_path / "client_secret.json"
        token_path = tmp_path / "token.json"

        client = GoogleDocsClient.from_local_credentials(
            client_secret_path=client_secret_path,
            token_path=token_path,
            include_drive=True,
        )

        assert mock_build.call_args_list == [
            mocker.call("docs", "v1", credentials=fake_creds),
            mocker.call("drive", "v3", credentials=fake_creds),
        ]
        assert client._service is fake_docs_service
        assert client._drive_service is fake_drive_service


class TestGoogleDocsClientFromAccessToken:
    """Tests that from_access_token wires a bearer token into build()."""

    def test_builds_docs_v1_service_with_credentials_from_the_token(
        self, mocker: MockerFixture
    ) -> None:
        """from_access_token wraps the token in Credentials and builds docs v1."""
        fake_creds = MagicMock()
        fake_service = MagicMock()
        mock_credentials_cls = mocker.patch(
            "verbatim.docs_client.Credentials", return_value=fake_creds
        )
        mock_build = mocker.patch(
            "verbatim.docs_client.build", return_value=fake_service
        )

        client = GoogleDocsClient.from_access_token("fake-token")

        mock_credentials_cls.assert_called_once_with(token="fake-token")
        mock_build.assert_called_once_with("docs", "v1", credentials=fake_creds)
        assert client._service is fake_service
        assert client._drive_service is None

    def test_also_builds_drive_v3_service_when_include_drive_is_true(
        self, mocker: MockerFixture
    ) -> None:
        """include_drive=True also builds a Drive v3 service with the same creds."""
        fake_creds = MagicMock()
        fake_docs_service = MagicMock()
        fake_drive_service = MagicMock()
        mocker.patch("verbatim.docs_client.Credentials", return_value=fake_creds)
        mock_build = mocker.patch(
            "verbatim.docs_client.build",
            side_effect=[fake_docs_service, fake_drive_service],
        )

        client = GoogleDocsClient.from_access_token("fake-token", include_drive=True)

        assert mock_build.call_args_list == [
            mocker.call("docs", "v1", credentials=fake_creds),
            mocker.call("drive", "v3", credentials=fake_creds),
        ]
        assert client._service is fake_docs_service
        assert client._drive_service is fake_drive_service


class TestGoogleDocsClientCache:
    """Tests the caching and invalidation behavior of GoogleDocsClient."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def fake_drive_service(self) -> MagicMock:
        """A fake Drive API discovery service, defaulting to non-Editor access."""
        drive_service = MagicMock()
        drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": False}
        }
        return drive_service

    @pytest.fixture
    def client(
        self, fake_service: MagicMock, fake_drive_service: MagicMock
    ) -> GoogleDocsClient:
        """A GoogleDocsClient wired to both fake services."""
        return GoogleDocsClient(service=fake_service, drive_service=fake_drive_service)

    def test_caches_document_content(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """Fetching document content twice only queries the API once."""
        get_doc = fake_service.documents.return_value.get
        get_doc.reset_mock()

        # First fetch - queries API
        doc1 = client.get_document_content("doc-id")
        assert doc1.title == "Q3 Launch Blog Draft"
        assert get_doc.call_count == 1

        # Second fetch - uses cache
        doc2 = client.get_document_content("doc-id")
        assert doc2.title == "Q3 Launch Blog Draft"
        assert get_doc.call_count == 1  # count remains 1

    def test_invalidates_cache_on_suggestion(
        self, client: GoogleDocsClient, fake_service: MagicMock
    ) -> None:
        """Creating a suggestion invalidates the cache, forcing a refetch."""
        get_doc = fake_service.documents.return_value.get
        get_doc.reset_mock()

        # Seed cache
        client.get_document_content("doc-id")
        assert get_doc.call_count == 1

        # Create suggestion
        client.create_suggestion("doc-id", "feature", "new-feature")

        # Fetch again - must query API again
        client.get_document_content("doc-id")
        assert get_doc.call_count >= 2

    def test_invalidates_cache_on_comment_when_editing_directly(
        self,
        client: GoogleDocsClient,
        fake_service: MagicMock,
        fake_drive_service: MagicMock,
    ) -> None:
        """Creating a comment invalidates the cache if the account can edit directly."""
        get_doc = fake_service.documents.return_value.get
        get_doc.reset_mock()
        fake_drive_service.files.return_value.get.return_value.execute.return_value = {
            "capabilities": {"canEdit": True}
        }

        # Seed cache
        client.get_document_content("doc-id")
        assert get_doc.call_count == 1

        # Create comment
        client.create_inline_comment("doc-id", "feature", "Consider rephrasing.")

        # Fetch again - must query API again
        client.get_document_content("doc-id")
        assert get_doc.call_count >= 2


class TestGoogleDocsClientListComments:
    """Tests the list_comments method of GoogleDocsClient (Christina's rotation)."""

    @pytest.fixture
    def fake_service(self) -> MagicMock:
        """A fake Docs API discovery service returning a fixed document."""
        service = MagicMock()
        service.documents.return_value.get.return_value.execute.return_value = (
            _FAKE_DOCUMENT_WITH_INDICES
        )
        return service

    @pytest.fixture
    def client(self, fake_service: MagicMock) -> GoogleDocsClient:
        """A GoogleDocsClient wired to fake service."""
        return GoogleDocsClient(service=fake_service)

    def test_list_comments_raises_not_implemented(
        self, client: GoogleDocsClient
    ) -> None:
        """Calling list_comments raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            client.list_comments("doc-id")
        assert str(exc_info.value) == "Christina's rotation task"
