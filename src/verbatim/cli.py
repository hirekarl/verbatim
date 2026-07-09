"""Command-line interface for the Verbatim copy auditor."""

import argparse
import sys
from pathlib import Path

from verbatim.agent import Finding, run_agent
from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import WRITE_SCOPES, DocsClientError, GoogleDocsClient
from verbatim.llm_client import LLMClientError, OpenRouterClient
from verbatim.prompt import CATEGORY_LABELS


def main(args: list[str] | None = None) -> None:
    """Run the Verbatim audit agent via command line.

    Args:
        args: Optional list of CLI arguments. If None, uses sys.argv[1:].
    """
    parser = argparse.ArgumentParser(
        description=(
            "Audit marketing copy in Google Docs against brand guidelines "
            "and a campaign brief."
        )
    )
    parser.add_argument(
        "document_id",
        type=str,
        help="The Google Docs document ID of the draft to audit.",
    )
    parser.add_argument(
        "brief_id",
        type=str,
        help="The Google Docs document ID of the campaign brief.",
    )
    parser.add_argument(
        "-c",
        "--channel",
        type=str,
        default=None,
        help="Optional target marketing channel (e.g. email, blog, twitter).",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default="google/gemini-2.5-flash",
        help="OpenRouter model identifier (default: google/gemini-2.5-flash).",
    )
    parser.add_argument(
        "-g",
        "--guidelines",
        type=str,
        default=None,
        help="Optional path to custom brand_guidelines.json file.",
    )

    parsed_args = parser.parse_args(args)

    try:
        # Load brand guidelines
        guidelines_path = (
            Path(parsed_args.guidelines) if parsed_args.guidelines else None
        )
        brand_guidelines = BrandGuidelines(guidelines_path)

        # Initialize clients
        docs_client = GoogleDocsClient.from_local_credentials(
            scopes=WRITE_SCOPES,
            include_drive=True,
        )
        llm_client = OpenRouterClient.from_env(model=parsed_args.model)

        print("Starting audit run...")
        print(f"Document ID:     {parsed_args.document_id}")
        print(f"Campaign Brief:  {parsed_args.brief_id}")
        if parsed_args.channel:
            print(f"Target Channel:  {parsed_args.channel}")
        print(f"LLM Model:       {parsed_args.model}")
        print("-" * 50)

        # Run agent
        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id=parsed_args.document_id,
            brief_id=parsed_args.brief_id,
            brand_guidelines=brand_guidelines,
            target_channel=parsed_args.channel,
        )

        # Print summary
        print("\n" + "=" * 50)
        print("AUDIT RUN SUMMARY")
        print("=" * 50)
        print(f"Suggestions posted: {result.suggestions_made}")
        print(f"Comments posted:    {result.comments_made}")
        cap_hit_str = (
            "Yes (stopped early)" if result.stopped_due_to_max_rounds else "No"
        )
        print(f"Max rounds cap hit: {cap_hit_str}")
        print("=" * 50)

        if result.findings:
            print("\nFindings:")
            by_category: dict[str, list[Finding]] = {}
            for finding in result.findings:
                by_category.setdefault(finding.category, []).append(finding)
            for category, category_findings in by_category.items():
                print(f"\n{CATEGORY_LABELS.get(category, category)}:")
                for finding in category_findings:
                    kind_label = (
                        "Suggestion" if finding.kind == "suggestion" else "Comment"
                    )
                    detail = f" -- {finding.detail}" if finding.detail else ""
                    print(f'  [{kind_label}] "{finding.matched_text}"{detail}')

    except (
        DocsClientError,
        LLMClientError,
        FileNotFoundError,
        ValueError,
        KeyError,
    ) as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"Unexpected error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
