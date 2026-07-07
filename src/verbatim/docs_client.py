"""Google Docs API client: auth plus read-side document/campaign-brief tools."""

from dataclasses import dataclass
from typing import Any

from googleapiclient.errors import HttpError


class DocsClientError(Exception):
    """Base exception for all docs_client failures."""


class AuthenticationError(DocsClientError):
    """Raised when loading, refreshing, or obtaining OAuth credentials fails."""


class DocumentNotFoundError(DocsClientError):
    """Raised when a requested document ID doesn't exist (HTTP 404)."""


class DocumentAccessDeniedError(DocsClientError):
    """Raised when a requested document exists but isn't shared (HTTP 403)."""


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

        paragraph_text = "".join(
            element.get("textRun", {}).get("content", "")
            for element in paragraph.get("elements", [])
        )
        body_text += paragraph_text

        named_style_type = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
        if named_style_type.startswith("HEADING_"):
            level = int(named_style_type.removeprefix("HEADING_"))
            headings.append(Heading(level=level, text=paragraph_text))

    return title, body_text, headings


class GoogleDocsClient:
    """A thin, read-side wrapper around the Google Docs API v1 client."""

    def __init__(self, service: Any) -> None:
        """Wrap an already-authenticated Docs API discovery service.

        Args:
            service: A Docs API v1 discovery ``Resource``, as returned by
                ``googleapiclient.discovery.build("docs", "v1", ...)``.
        """
        self._service = service

    def get_document_content(self, document_id: str) -> DocumentContent:
        """Fetch and parse the audited document's content.

        Args:
            document_id: The Google Docs document ID being audited.

        Returns:
            The document's title, body text, and headings.
        """
        document = _fetch_document(self._service, document_id)
        title, body_text, headings = _extract_title_body_and_headings(document)
        return DocumentContent(
            document_id=document_id,
            title=title,
            body_text=body_text,
            headings=headings,
        )
