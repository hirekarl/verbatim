"""Google Docs API client: auth plus read-side document/campaign-brief tools."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DEFAULT_SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]
WRITE_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

_HIGHLIGHT_BACKGROUND_COLOR = {
    "color": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 0.0}}
}
_REPLACEMENT_TEXT_COLOR = {
    "color": {"rgbColor": {"red": 0.0, "green": 0.6, "blue": 0.0}}
}


class DocsClientError(Exception):
    """Base exception for all docs_client failures."""


class AuthenticationError(DocsClientError):
    """Raised when loading, refreshing, or obtaining OAuth credentials fails."""


class DocumentNotFoundError(DocsClientError):
    """Raised when a requested document ID doesn't exist (HTTP 404)."""


class DocumentAccessDeniedError(DocsClientError):
    """Raised when a requested document exists but isn't shared (HTTP 403)."""


class TextNotFoundError(DocsClientError):
    """Raised when a suggestion/comment target substring isn't found in the doc."""


class AmbiguousMatchError(DocsClientError):
    """Raised when a suggestion/comment target substring isn't unique in the doc."""


@dataclass(frozen=True)
class Heading:
    """A single heading extracted from a document's structural content."""

    level: int
    text: str


@dataclass(frozen=True)
class DocumentContent:
    """The parsed content of an audited marketing-copy document."""

    document_id: str
    title: str
    body_text: str
    headings: list[Heading]


@dataclass(frozen=True)
class CampaignContext:
    """The parsed content of a campaign brief document.

    Structurally identical to DocumentContent today, but kept as a distinct
    type: no sample brief exists yet to design a parsed-field schema
    (audience/channel/CTA requirements/goals) against, so this type is a seam
    for that to be added later without touching DocumentContent or any call
    site that consumes it.
    """

    document_id: str
    title: str
    body_text: str
    headings: list[Heading]


def _fetch_document(service: Any, document_id: str) -> dict[str, Any]:
    """Fetch a document's raw JSON via the Docs API, mapping HTTP errors.

    Args:
        service: An authenticated Docs API v1 discovery ``Resource``.
        document_id: The Google Docs document ID to fetch.

    Returns:
        The raw document JSON payload as returned by ``documents.get``.

    Raises:
        DocumentNotFoundError: The document ID doesn't exist (HTTP 404).
        DocumentAccessDeniedError: The document exists but isn't accessible
            to the authenticated account (HTTP 403).
        DocsClientError: Any other API failure.
    """
    try:
        result: dict[str, Any] = (
            service.documents().get(documentId=document_id).execute()
        )
        return result
    except HttpError as err:
        if err.resp.status == 404:
            raise DocumentNotFoundError(f"Document not found: {document_id}") from err
        if err.resp.status == 403:
            raise DocumentAccessDeniedError(
                f"Access denied for document: {document_id}"
            ) from err
        raise DocsClientError(f"Failed to fetch document: {document_id}") from err


def _execute_batch_update(
    service: Any, document_id: str, requests: list[dict[str, Any]], error_message: str
) -> None:
    """Execute a documents.batchUpdate call, mapping HttpErrors to DocsClientError.

    Args:
        service: An authenticated Docs API v1 discovery ``Resource``.
        document_id: The Google Docs document ID to update.
        requests: The batch's list of update request dicts.
        error_message: The message to raise as ``DocsClientError`` on failure.

    Raises:
        DocsClientError: The batch update failed.
    """
    try:
        service.documents().batchUpdate(
            documentId=document_id, body={"requests": requests}
        ).execute()
    except HttpError as err:
        raise DocsClientError(error_message) from err


def _extract_paragraph_clean_text(paragraph: dict[str, Any]) -> str:
    """Extract paragraph text ignoring struck-through elements."""
    clean_text = ""
    for element in paragraph.get("elements", []):
        text_run = element.get("textRun")
        if text_run is None:
            continue
        is_strikethrough = text_run.get("textStyle", {}).get("strikethrough", False)
        if is_strikethrough:
            continue
        clean_text += text_run.get("content", "")
    return clean_text


def _extract_paragraph_clean_text_and_map(
    paragraph: dict[str, Any], paragraph_start: int
) -> tuple[str, list[int]]:
    """Extract clean text and map each character's Python index to Doc UTF-16 index."""
    clean_text = ""
    index_map = []
    current_doc_idx = paragraph_start

    for element in paragraph.get("elements", []):
        text_run = element.get("textRun")
        if text_run is None:
            current_doc_idx += 1
            continue

        is_strikethrough = text_run.get("textStyle", {}).get("strikethrough", False)
        content = text_run.get("content", "")
        content_len = _utf16_length(content)

        if is_strikethrough:
            current_doc_idx += content_len
            continue

        for char in content:
            char_utf16_len = _utf16_length(char)
            clean_text += char
            index_map.append(current_doc_idx)
            current_doc_idx += char_utf16_len

    return clean_text, index_map


def _extract_title_body_and_headings(
    document: dict[str, Any],
) -> tuple[str, str, list[Heading]]:
    """Parse a Docs API document JSON payload into title, body text, and headings.

    Args:
        document: The raw JSON body returned by ``documents.get``.

    Returns:
        A tuple of the document's title, its concatenated body text, and the
        list of headings found, in document order.
    """
    title: str = document.get("title", "")
    body_text = ""
    headings: list[Heading] = []

    for structural_element in document.get("body", {}).get("content", []):
        paragraph = structural_element.get("paragraph")
        if paragraph is None:
            continue

        paragraph_text = _extract_paragraph_clean_text(paragraph)
        body_text += paragraph_text

        named_style_type = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
        if named_style_type.startswith("HEADING_"):
            level = int(named_style_type.removeprefix("HEADING_"))
            headings.append(Heading(level=level, text=paragraph_text))

    return title, body_text, headings


@dataclass(frozen=True)
class _TextChunk:
    """A single paragraph's clean text and mapping to original doc indices."""

    start_index: int
    text: str
    index_map: list[int]


def _extract_text_chunks(document: dict[str, Any]) -> list[_TextChunk]:
    """Split a document's body into per-paragraph chunks for range lookup.

    Args:
        document: The raw JSON body returned by ``documents.get``.

    Returns:
        One chunk per paragraph, in document order, containing clean text
        and doc index mapping.
    """
    chunks: list[_TextChunk] = []
    for structural_element in document.get("body", {}).get("content", []):
        paragraph = structural_element.get("paragraph")
        if paragraph is None:
            continue

        paragraph_start = structural_element.get("startIndex", 0)
        text, index_map = _extract_paragraph_clean_text_and_map(
            paragraph, paragraph_start
        )
        chunks.append(
            _TextChunk(start_index=paragraph_start, text=text, index_map=index_map)
        )

    return chunks


def _utf16_length(text: str) -> int:
    """Return the number of UTF-16 code units ``text`` occupies."""
    return len(text.encode("utf-16-le")) // 2


def _locate_document_range(
    document: dict[str, Any], matched_text: str
) -> tuple[int, int]:
    """Find the unique UTF-16 [start, end) range of ``matched_text`` in the document.

    Searches each paragraph independently, so a match spanning a paragraph
    break is not supported.

    Args:
        document: The raw JSON body returned by ``documents.get``.
        matched_text: The exact substring to locate.

    Returns:
        The ``(start_index, end_index)`` UTF-16 range of the match.

    Raises:
        TextNotFoundError: ``matched_text`` appears nowhere in the document.
        AmbiguousMatchError: ``matched_text`` appears more than once.
    """
    found: list[tuple[int, int]] = []

    for chunk in _extract_text_chunks(document):
        search_from = 0
        while (offset := chunk.text.find(matched_text, search_from)) != -1:
            match_end = offset + len(matched_text)
            start = chunk.index_map[offset]
            if match_end < len(chunk.text):
                end = chunk.index_map[match_end]
            else:
                last_char_idx = chunk.index_map[match_end - 1]
                last_char = chunk.text[match_end - 1]
                end = last_char_idx + _utf16_length(last_char)

            found.append((start, end))
            search_from = offset + 1

    if not found:
        raise TextNotFoundError(f"Text not found in document: {matched_text!r}")
    if len(found) > 1:
        raise AmbiguousMatchError(
            f"Text appears {len(found)} times in document, must be unique: "
            f"{matched_text!r}"
        )
    return found[0]


def _load_credentials(
    client_secret_path: Path, token_path: Path, scopes: list[str]
) -> Credentials:
    """Load cached OAuth credentials, refreshing or requesting consent as needed.

    Args:
        client_secret_path: Path to the downloaded Google Cloud OAuth client
            secret JSON file.
        token_path: Path where a previously-obtained token is cached, and
            where a newly obtained/refreshed token gets persisted.
        scopes: The OAuth scopes to request.

    Returns:
        Valid, usable OAuth credentials.

    Raises:
        AuthenticationError: The client secret file is missing, the cached
            token failed to refresh, or the consent flow failed to complete.
    """
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_path), scopes
        )

    if creds is not None and creds.valid:
        return creds

    if creds is not None and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())  # type: ignore[no-untyped-call]
        except Exception as err:
            raise AuthenticationError(
                "Failed to refresh Google OAuth credentials"
            ) from err
    else:
        if not client_secret_path.exists():
            raise AuthenticationError(
                f"Client secret file not found: {client_secret_path}"
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), scopes
            )
            creds = flow.run_local_server(port=0)
        except Exception as err:
            raise AuthenticationError(
                "Failed to complete Google OAuth consent flow"
            ) from err

    assert creds is not None  # narrows for mypy; set by one of the branches above
    token_path.write_text(creds.to_json())
    return creds


class GoogleDocsClient:
    """A thin, read-side wrapper around the Google Docs API v1 client."""

    def __init__(self, service: Any, drive_service: Any | None = None) -> None:
        """Wrap already-authenticated Docs (and optionally Drive) discovery services.

        Args:
            service: A Docs API v1 discovery ``Resource``, as returned by
                ``googleapiclient.discovery.build("docs", "v1", ...)``.
            drive_service: A Drive API v3 discovery ``Resource``, required
                only for ``create_inline_comment`` (comments are a Drive
                resource, not a Docs one). Omit if only reading/suggesting.
        """
        self._service = service
        self._drive_service = drive_service
        self._doc_cache: dict[str, dict[str, Any]] = {}

    def _get_cached_document(self, document_id: str) -> dict[str, Any]:
        """Fetch a document, retrieving from cache if present.

        Args:
            document_id: The document ID to fetch.

        Returns:
            The raw document JSON payload.
        """
        if document_id not in self._doc_cache:
            self._doc_cache[document_id] = _fetch_document(self._service, document_id)
        return self._doc_cache[document_id]

    def clear_cache(self, document_id: str | None = None) -> None:
        """Clear cached documents.

        Args:
            document_id: If specified, clears only the cache for this document ID.
                If None, clears all cached documents.
        """
        if document_id is not None:
            self._doc_cache.pop(document_id, None)
        else:
            self._doc_cache.clear()

    @classmethod
    def from_local_credentials(
        cls,
        client_secret_path: Path | None = None,
        token_path: Path | None = None,
        scopes: list[str] | None = None,
        include_drive: bool = False,
    ) -> "GoogleDocsClient":
        """Build a client using locally cached/obtained OAuth credentials.

        Args:
            client_secret_path: Path to the downloaded Google Cloud OAuth
                client secret JSON. Defaults to ``client_secret.json`` in the
                current working directory.
            token_path: Path to cache the obtained/refreshed token at.
                Defaults to ``token.json`` in the current working directory.
            scopes: OAuth scopes to request. Defaults to
                ``DEFAULT_SCOPES`` (read-only document access). Pass
                ``WRITE_SCOPES`` for ``create_suggestion``/
                ``create_inline_comment`` support.
            include_drive: Also build a Drive API v3 service from the same
                credentials, required for ``create_inline_comment``.

        Returns:
            A GoogleDocsClient backed by an authenticated Docs API v1 service
            (and a Drive API v3 service, if ``include_drive`` is set).
        """
        resolved_client_secret_path = client_secret_path or Path("client_secret.json")
        resolved_token_path = token_path or Path("token.json")
        resolved_scopes = scopes if scopes is not None else DEFAULT_SCOPES
        credentials = _load_credentials(
            resolved_client_secret_path, resolved_token_path, resolved_scopes
        )
        service = build("docs", "v1", credentials=credentials)
        drive_service = (
            build("drive", "v3", credentials=credentials) if include_drive else None
        )
        return cls(service=service, drive_service=drive_service)

    @classmethod
    def from_access_token(
        cls, token: str, include_drive: bool = False
    ) -> "GoogleDocsClient":
        """Build a client from a bearer token handed to a hosted backend per-request.

        For a Workspace Add-on backend: the caller (an Apps Script Add-on via
        ``ScriptApp.getOAuthToken()``) already holds a valid OAuth access
        token for the current user, so no local consent flow or token cache
        is needed here — this wraps the token directly and builds the same
        Docs (and optionally Drive) services ``from_local_credentials`` does.

        Args:
            token: A valid Google OAuth access token, forwarded by the
                caller on each request.
            include_drive: Also build a Drive API v3 service from the same
                token, required for ``create_inline_comment`` support.

        Returns:
            A GoogleDocsClient backed by an authenticated Docs API v1 service
            (and a Drive API v3 service, if ``include_drive`` is set).
        """
        credentials = Credentials(token=token)  # type: ignore[no-untyped-call]
        service = build("docs", "v1", credentials=credentials)
        drive_service = (
            build("drive", "v3", credentials=credentials) if include_drive else None
        )
        return cls(service=service, drive_service=drive_service)

    def get_document_content(self, document_id: str) -> DocumentContent:
        """Fetch and parse the audited document's content.

        Args:
            document_id: The Google Docs document ID being audited.

        Returns:
            The document's title, body text, and headings.
        """
        document = self._get_cached_document(document_id)
        title, body_text, headings = _extract_title_body_and_headings(document)
        return DocumentContent(
            document_id=document_id,
            title=title,
            body_text=body_text,
            headings=headings,
        )

    def get_campaign_context(self, brief_id: str) -> CampaignContext:
        """Fetch and parse the campaign brief document's content.

        Args:
            brief_id: The Google Docs document ID of the campaign brief (a
                document distinct from the one being audited).

        Returns:
            The brief's title, body text, and headings.
        """
        document = self._get_cached_document(brief_id)
        title, body_text, headings = _extract_title_body_and_headings(document)
        return CampaignContext(
            document_id=brief_id,
            title=title,
            body_text=body_text,
            headings=headings,
        )

    def _can_edit_directly(self, document_id: str) -> bool:
        """Check whether the authenticated account has Editor access to a file.

        Used by ``create_suggestion`` and ``create_inline_comment`` to decide
        whether a batchUpdate would land as a reviewable suggestion
        (Commenter/Suggester) or a silent direct edit (Editor) — the Docs API
        has no explicit suggestion-mode request flag, so this is the only way
        to tell in advance.

        Args:
            document_id: The Google Docs (Drive file) ID to check.

        Returns:
            True if the account can edit the file directly.
        """
        assert self._drive_service is not None
        result = (
            self._drive_service.files()
            .get(fileId=document_id, fields="capabilities(canEdit)")
            .execute()
        )
        can_edit: bool = result.get("capabilities", {}).get("canEdit", False)
        return can_edit

    def create_suggestion(
        self, document_id: str, matched_text: str, replacement_text: str
    ) -> None:
        """Propose a suggested edit replacing an exact substring of the document.

        Whether this lands as a Google Docs "suggestion" (advisory, must be
        accepted) versus a direct edit depends on the OAuth principal's
        sharing role on the document (Commenter/Suggester vs. Editor) — the
        Docs API has no explicit suggestion-mode request flag. When a Drive
        service is configured, this is checked in advance: an Editor-capable
        account gets the original text struck through with the replacement
        inserted after it in bold, instead of a silent, un-reviewable direct
        edit.

        Args:
            document_id: The Google Docs document ID to edit.
            matched_text: The exact, unique substring to replace.
            replacement_text: The text to replace it with. An empty string
                marks a pure cut (strikethrough only, nothing inserted).

        Raises:
            TextNotFoundError: ``matched_text`` doesn't appear in the document.
            AmbiguousMatchError: ``matched_text`` appears more than once.
            DocsClientError: The document fetch or batch update failed.
        """
        document = self._get_cached_document(document_id)
        start, end = _locate_document_range(document, matched_text)

        if self._drive_service is not None and self._can_edit_directly(document_id):
            requests: list[dict[str, Any]] = [
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"strikethrough": True},
                        "fields": "strikethrough",
                    }
                }
            ]
            if replacement_text:
                insertion_length = _utf16_length(replacement_text)
                requests.append(
                    {
                        "insertText": {
                            "location": {"index": end},
                            "text": replacement_text,
                        }
                    }
                )
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": end,
                                "endIndex": end + insertion_length,
                            },
                            "textStyle": {
                                "bold": True,
                                "strikethrough": False,
                                "foregroundColor": _REPLACEMENT_TEXT_COLOR,
                            },
                            "fields": "bold,strikethrough,foregroundColor",
                        }
                    }
                )
        else:
            requests = [
                {
                    "deleteContentRange": {
                        "range": {"startIndex": start, "endIndex": end}
                    }
                },
                {
                    "insertText": {
                        "location": {"index": start},
                        "text": replacement_text,
                    }
                },
            ]

        _execute_batch_update(
            self._service,
            document_id,
            requests,
            f"Failed to create suggestion in document: {document_id}",
        )
        self.clear_cache(document_id)

    def create_inline_comment(
        self, document_id: str, matched_text: str, comment: str
    ) -> None:
        """Attach an explanatory comment referencing an exact document substring.

        Comments on a Drive-hosted file are a Drive API v3 resource, not a
        Docs API one, so this requires a Drive service to have been supplied
        at construction time. The comment isn't anchored to a precise text
        range in the Drive UI (Drive's ``anchor`` field uses an unconfirmed,
        largely undocumented JSON micro-schema) — instead, ``matched_text``
        is quoted in the comment body so the copywriter can find it. On an
        Editor-capable account, the matched span is also highlighted in the
        document itself, since such an account can't get a native Docs
        comment-anchor highlight either way.

        Args:
            document_id: The Google Docs (Drive file) ID to comment on.
            matched_text: The exact, unique substring this comment refers to.
            comment: The explanatory comment body.

        Raises:
            DocsClientError: No Drive service was configured, or the document
                fetch/comment creation failed.
            TextNotFoundError: ``matched_text`` doesn't appear in the document.
            AmbiguousMatchError: ``matched_text`` appears more than once.
        """
        if self._drive_service is None:
            raise DocsClientError(
                "create_inline_comment requires a Drive API service - construct "
                "GoogleDocsClient with drive_service or "
                "from_local_credentials(include_drive=True)."
            )
        document = self._get_cached_document(document_id)
        start, end = _locate_document_range(document, matched_text)
        body = {"content": f'Re: "{matched_text}"\n\n{comment}'}
        try:
            self._drive_service.comments().create(
                fileId=document_id, body=body, fields="id"
            ).execute()
        except HttpError as err:
            raise DocsClientError(
                f"Failed to create comment on document: {document_id}"
            ) from err

        if self._can_edit_directly(document_id):
            _execute_batch_update(
                self._service,
                document_id,
                [
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "textStyle": {
                                "backgroundColor": _HIGHLIGHT_BACKGROUND_COLOR
                            },
                            "fields": "backgroundColor",
                        }
                    }
                ],
                f"Failed to highlight matched text in document: {document_id}",
            )
            self.clear_cache(document_id)

    def list_comments(self, document_id: str) -> list[dict[str, Any]]:
        """List comments on a Google Drive file.

        To be implemented by Christina as part of her post-demo rotation.

        Args:
            document_id: The document ID to fetch comments for.

        Returns:
            A list of comment dictionaries.

        Raises:
            NotImplementedError: Always, until implemented.
        """
        raise NotImplementedError("Christina's rotation task")
