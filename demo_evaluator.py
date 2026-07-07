"""Demo script showing how to use the BrandGuidelinesEvaluator."""

from verbatim.evaluator import BrandGuidelinesEvaluator


def main() -> None:
    """Run the evaluator on sample marketing copy."""
    # Initialize the evaluator
    evaluator = BrandGuidelinesEvaluator("brand_guidelines.json")

    # Sample marketing copy with various issues
    sample_text = """
    We need to leverage our platform to incentivize growth.

    Check out our templates & automation features for your business.

    Our platform offers templates, automation and analytics to help you grow.

    We're crushing it with our new features!
    """

    print("=" * 70)
    print("BRAND GUIDELINES EVALUATOR DEMO")
    print("=" * 70)
    print("\nSample Marketing Copy:")
    print("-" * 70)
    print(sample_text)
    print("-" * 70)

    # Evaluate the text
    violations = evaluator.evaluate(sample_text)

    print(f"\nFound {len(violations)} violation(s):\n")

    # Display violations grouped by category
    categories: dict[str, list] = {}
    for violation in violations:
        if violation.category not in categories:
            categories[violation.category] = []
        categories[violation.category].append(violation)

    for category, viols in categories.items():
        print(f"\n{category.upper().replace('_', ' ')}")
        print("   " + "-" * 65)
        for v in viols:
            severity_label = {"error": "[ERROR]", "warning": "[WARN]", "info": "[INFO]"}
            print(f"   {severity_label[v.severity]} {v.message}")
            print(f"      Matched: '{v.matched_text}'")
            if v.suggestion:
                print(f"      Suggestion: {v.suggestion}")
            print()


if __name__ == "__main__":
    main()
