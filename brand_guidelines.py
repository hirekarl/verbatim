import json
import os
from typing import Dict, List, Any, Optional

class BrandGuidelines:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Brand guidelines fixture not found at: {self.filepath}")
        
        with open(self.filepath, "r", encoding="utf-8") as f:
            try:
                self.data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in brand guidelines file: {e}")
        
        # Verify basic expected schema
        expected_keys = ["metadata", "voice_and_tone", "rules"]
        for key in expected_keys:
            if key not in self.data:
                raise KeyError(f"Missing expected root key in brand guidelines: '{key}'")

    def get_voice_and_tone_summary(self) -> str:
        """Formats voice principles and tone guidelines as a clean Markdown string."""
        vt = self.data.get("voice_and_tone", {})
        lines = ["### Voice Principles:"]
        for name, desc in vt.get("voice_principles", {}).items():
            lines.append(f"- **{name.capitalize()}**: {desc}")
            
        lines.append("\n### Tone Guidance:")
        for name, desc in vt.get("tone_guidance", {}).items():
            clean_name = name.replace("_", " ").capitalize()
            lines.append(f"- **{clean_name}**: {desc}")
            
        return "\n".join(lines)

    def get_rules_for_category(self, category: str) -> List[str]:
        """Returns the list of rules for a specific category (e.g., 'readability', 'formatting_and_style')."""
        rules_dict = self.data.get("rules", {})
        cat_data = rules_dict.get(category, {})
        if isinstance(cat_data, dict):
            return cat_data.get("rules", [])
        return []

    def get_banned_words(self) -> List[str]:
        """Returns the list of banned words."""
        rules_dict = self.data.get("rules", {})
        bwc = rules_dict.get("banned_words_and_competitors", {})
        return bwc.get("banned_words", [])

    def get_standardized_spellings(self) -> Dict[str, str]:
        """Returns the dictionary of standardized spellings."""
        rules_dict = self.data.get("rules", {})
        bwc = rules_dict.get("banned_words_and_competitors", {})
        return bwc.get("standardized_spellings", {})

    def format_for_llm_prompt(self, target_channel: Optional[str] = None) -> str:
        """
        Synthesizes the rules into a highly structured, token-efficient Markdown prompt block
        that the LLM can easily ingest. Optionally filters by a target channel.
        """
        prompt = []
        prompt.append("=== BRAND VOICE & STYLE GUIDELINES ===")
        prompt.append(self.get_voice_and_tone_summary())
        prompt.append("")
        
        prompt.append("### Core Audit Rules:")
        
        # Add rules by category
        categories = ["tone_drift", "information_hierarchy", "cta_cadence", "readability", "formatting_and_style"]
        for cat in categories:
            rules = self.get_rules_for_category(cat)
            if rules:
                cat_name = cat.replace("_", " ").upper()
                prompt.append(f"\n* {cat_name}:")
                for rule in rules:
                    prompt.append(f"  - {rule}")
                    
        # Add channel constraints if target_channel is provided
        if target_channel:
            cc_rules = self.get_rules_for_category("channel_constraints")
            matching_rules = [r for r in cc_rules if target_channel.lower() in r.lower()]
            if matching_rules:
                prompt.append("\n* CHANNEL-SPECIFIC CONSTRAINTS:")
                for rule in matching_rules:
                    prompt.append(f"  - {rule}")
                    
        # Add Banned Words & Spellings
        banned = self.get_banned_words()
        if banned:
            prompt.append(f"\n* BANNED WORDS (Do not use under any circumstances): {', '.join(banned)}")
            
        spellings = self.get_standardized_spellings()
        if spellings:
            prompt.append("\n* STANDARDIZED SPELLINGS & USAGE:")
            for term, rule in spellings.items():
                prompt.append(f"  - **{term}**: {rule}")
                
        prompt.append("======================================")
        return "\n".join(prompt)

if __name__ == "__main__":
    # Quick self-test
    try:
        bg = BrandGuidelines("brand_guidelines.json")
        print("Success: Loaded guidelines!")
        print("\nPreview of LLM Prompt Injection Block:")
        print(bg.format_for_llm_prompt(target_channel="twitter")[:600] + "...\n[Truncated]")
    except Exception as e:
        print(f"Error testing interface: {e}")
