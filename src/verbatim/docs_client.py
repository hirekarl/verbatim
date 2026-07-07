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

    def __init__(self, service: Any) -> None:
        """Wrap an already-authenticated Docs API discovery service.

        Args:
            service: A Docs API v1 discovery ``Resource``, as returned by
                ``googleapiclient.discovery.build("docs", "v1", ...)``.
        """
        self._service = service

    @classmethod
    def from_local_credentials(
        cls,
        client_secret_path: Path | None = None,
        token_path: Path | None = None,
        scopes: list[str] | None = None,
    ) -> "GoogleDocsClient":
        """Build a client using locally cached/obtained OAuth credentials.

        Args:
            client_secret_path: Path to the downloaded Google Cloud OAuth
                client secret JSON. Defaults to ``client_secret.json`` in the
                current working directory.
            token_path: Path to cache the obtained/refreshed token at.
                Defaults to ``token.json`` in the current working directory.
            scopes: OAuth scopes to request. Defaults to
                ``DEFAULT_SCOPES`` (read-only document access).

        Returns:
            A GoogleDocsClient backed by an authenticated Docs API v1 service.
        """
        resolved_client_secret_path = client_secret_path or Path("client_secret.json")
        resolved_token_path = token_path or Path("token.json")
        resolved_scopes = scopes if scopes is not None else DEFAULT_SCOPES
        credentials = _load_credentials(
            resolved_client_secret_path, resolved_token_path, resolved_scopes
        )
        service = build("docs", "v1", credentials=credentials)
        return cls(service=service)

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

    def get_campaign_context(self, brief_id: str) -> CampaignContext:
        """Fetch and parse the campaign brief document's content.

        Args:
            brief_id: The Google Docs document ID of the campaign brief (a
                document distinct from the one being audited).

        Returns:
            The brief's title, body text, and headings.
        """
        document = _fetch_document(self._service, brief_id)
        title, body_text, headings = _extract_title_body_and_headings(document)
        return CampaignContext(
            document_id=brief_id,
            title=title,
            body_text=body_text,
            headings=headings,
        )
