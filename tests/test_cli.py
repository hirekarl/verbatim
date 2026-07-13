"""Tests for the Verbatim CLI entrypoint."""

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from verbatim.agent import AgentRunResult, Finding
from verbatim.cli import main
from verbatim.docs_client import DocsClientError
from verbatim.llm_client import LLMClientError


class TestCLI:
    """Tests for the Verbatim CLI entrypoint."""

    @pytest.fixture
    def mock_run_agent(self, mocker: MockerFixture) -> MagicMock:
        """Mock the run_agent function."""
        return mocker.patch("verbatim.cli.run_agent")

    @pytest.fixture
    def mock_docs_client(self, mocker: MockerFixture) -> MagicMock:
        """Mock the GoogleDocsClient class and its from_local_credentials method."""
        mock_cls = mocker.patch("verbatim.cli.GoogleDocsClient")
        return cast(MagicMock, mock_cls.from_local_credentials)

    @pytest.fixture
    def mock_llm_client(self, mocker: MockerFixture) -> MagicMock:
        """Mock the OpenRouterClient class and its from_env method."""
        mock_cls = mocker.patch("verbatim.cli.OpenRouterClient")
        return cast(MagicMock, mock_cls.from_env)

    @pytest.fixture
    def mock_brand_guidelines(self, mocker: MockerFixture) -> MagicMock:
        """Mock the BrandGuidelines class."""
        return mocker.patch("verbatim.cli.BrandGuidelines")

    def test_cli_success(
        self,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI runs successfully and prints a summary when agent run completes."""
        fake_result = AgentRunResult(
            suggestions_made=3,
            comments_made=5,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )
        mock_run_agent.return_value = fake_result

        # Run with target channel, custom model, and custom guidelines
        main(
            [
                "doc-id",
                "brief-id",
                "--channel",
                "email",
                "--model",
                "custom/model",
                "--guidelines",
                "custom_rules.json",
            ]
        )

        mock_brand_guidelines.assert_called_once_with(Path("custom_rules.json"))
        mock_docs_client.assert_called_once_with(
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive",
            ],
            include_drive=True,
        )
        mock_llm_client.assert_called_once_with(model="custom/model")
        mock_run_agent.assert_called_once_with(
            docs_client=mock_docs_client.return_value,
            llm_client=mock_llm_client.return_value,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=mock_brand_guidelines.return_value,
            target_channel="email",
        )

        captured = capsys.readouterr()
        assert "Starting audit run..." in captured.out
        assert "Document ID:     doc-id" in captured.out
        assert "Campaign Brief:  brief-id" in captured.out
        assert "Target Channel:  email" in captured.out
        assert "LLM Model:       custom/model" in captured.out
        assert "AUDIT RUN SUMMARY" in captured.out
        assert "Suggestions posted: 3" in captured.out
        assert "Comments posted:    5" in captured.out
        assert "Max rounds cap hit: No" in captured.out

    def test_cli_prints_findings_grouped_by_category(
        self,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Each finding is printed with its category label, matched text, and detail."""
        fake_result = AgentRunResult(
            suggestions_made=1,
            comments_made=1,
            transcript=[],
            stopped_due_to_max_rounds=False,
            category_counts={"readability": 1, "information_hierarchy": 1},
            findings=[
                Finding(
                    category="readability",
                    kind="suggestion",
                    matched_text="Feature helps you",
                    detail="Passive voice; rewrite as active.",
                ),
                Finding(
                    category="information_hierarchy",
                    kind="comment",
                    matched_text="Big News!",
                    detail="Lead with value instead.",
                ),
            ],
        )
        mock_run_agent.return_value = fake_result

        main(["doc-id", "brief-id"])

        captured = capsys.readouterr()
        assert "Readability" in captured.out
        assert "Feature helps you" in captured.out
        assert "Passive voice; rewrite as active." in captured.out
        assert "Information Hierarchy" in captured.out
        assert "Big News!" in captured.out
        assert "Lead with value instead." in captured.out

    def test_cli_prints_cross_agent_overlaps_when_present(
        self,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Overlapping Structural/Line-Editor findings are flagged, not resolved."""
        structural_finding = Finding(
            category="cta_cadence",
            kind="comment",
            matched_text="Upgrade your plan.",
            detail="This CTA is premature.",
        )
        line_editor_finding = Finding(
            category="tone_drift",
            kind="suggestion",
            matched_text="Upgrade your plan.",
            detail="Soften the abrupt command.",
        )
        fake_result = AgentRunResult(
            suggestions_made=1,
            comments_made=1,
            transcript=[],
            stopped_due_to_max_rounds=False,
            findings=[structural_finding, line_editor_finding],
            cross_agent_overlaps=[(structural_finding, line_editor_finding)],
        )
        mock_run_agent.return_value = fake_result

        main(["doc-id", "brief-id"])

        captured = capsys.readouterr()
        assert "Cross-agent overlaps" in captured.out
        assert "Upgrade your plan." in captured.out
        assert "cta_cadence" in captured.out
        assert "tone_drift" in captured.out

    def test_cli_omits_cross_agent_overlaps_section_when_none_found(
        self,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """No overlap noise in the common case where nothing overlapped."""
        fake_result = AgentRunResult(
            suggestions_made=1,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )
        mock_run_agent.return_value = fake_result

        main(["doc-id", "brief-id"])

        captured = capsys.readouterr()
        assert "Cross-agent overlaps" not in captured.out

    def test_cli_success_defaults(
        self,
        mock_run_agent: MagicMock,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        mock_brand_guidelines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI runs successfully with default arguments."""
        fake_result = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=True,
        )
        mock_run_agent.return_value = fake_result

        main(["doc-id", "brief-id"])

        mock_brand_guidelines.assert_called_once_with(None)
        mock_docs_client.assert_called_once_with(
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive",
            ],
            include_drive=True,
        )
        mock_llm_client.assert_called_once_with(model="google/gemini-2.5-flash")
        mock_run_agent.assert_called_once_with(
            docs_client=mock_docs_client.return_value,
            llm_client=mock_llm_client.return_value,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=mock_brand_guidelines.return_value,
            target_channel=None,
        )

        captured = capsys.readouterr()
        assert "LLM Model:       google/gemini-2.5-flash" in captured.out
        assert "Target Channel" not in captured.out
        assert "Max rounds cap hit: Yes (stopped early)" in captured.out

    def test_cli_docs_client_error(
        self,
        mock_docs_client: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI prints DocsClientError and exits with code 1."""
        mock_docs_client.side_effect = DocsClientError("Auth failed")

        with pytest.raises(SystemExit) as exc_info:
            main(["doc-id", "brief-id"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Auth failed" in captured.err

    def test_cli_llm_client_error(
        self,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI prints LLMClientError and exits with code 1."""
        mock_llm_client.side_effect = LLMClientError("API key missing")

        with pytest.raises(SystemExit) as exc_info:
            main(["doc-id", "brief-id"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error: API key missing" in captured.err

    def test_cli_unexpected_error(
        self,
        mock_docs_client: MagicMock,
        mock_llm_client: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI prints unexpected exceptions and exits with code 1."""
        mock_llm_client.side_effect = RuntimeError("Something bad happened")

        with pytest.raises(SystemExit) as exc_info:
            main(["doc-id", "brief-id"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Unexpected error: Something bad happened" in captured.err
