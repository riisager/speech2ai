import json
import re
import os
import sys

class CustomDictionary:
    def __init__(self, filepath="vocabulary.json"):
        self.filepath = filepath
        self.dictionary = self.load()
        # Sort keys by length (descending) so longer multi-word phrases are matched
        # and replaced before shorter individual words. Done once in constructor.
        self.sorted_keys = sorted(self.dictionary.keys(), key=len, reverse=True)

    def load(self):
        """Loads custom vocabulary definitions from JSON."""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading vocabulary from {self.filepath}: {e}", file=sys.stderr)
            
        # Default fallback dictionary
        default = {
            "pimplify": "PIMplify",
            "git hub": "GitHub",
            "æpi": "API",
            "antigravity": "Antigravity",
            "nocoffee": "NoCoffee",
            "cursor": "Cursor"
        }
        
        # Try to save the default dictionary
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Could not write default vocabulary to {self.filepath}: {e}", file=sys.stderr)
            
        return default

    def clean_text(self, text):
        """Applies word replacements based on the loaded dictionary."""
        if not text:
            return ""
            
        cleaned = text
        for key in self.sorted_keys:
            # We use \b to match word boundaries. This ensures we don't match subparts of words
            # (e.g., matching "cursor" inside "precursor").
            # Note: Python's re module supports unicode boundaries naturally in Python 3.
            pattern = re.compile(rf'\b{re.escape(key)}\b', re.IGNORECASE)
            cleaned = pattern.sub(self.dictionary[key], cleaned)
            
        # Remove Danish/English hesitation/filler words (øh, øhh, øhm, æh, æhm, uh, um, uhm, etc.)
        filler_pattern = re.compile(r'\b(øh+m?|æh+m?|uh+m?|um)\b', re.IGNORECASE)
        cleaned = filler_pattern.sub("", cleaned)
        
        # Clean up punctuation and spaces around removed filler words:
        # 1. Remove space before punctuation (e.g., "ord , og" -> "ord, og")
        cleaned = re.sub(r'\s+([,.:;?!])', r'\1', cleaned)
        # 2. Collapse duplicate commas (e.g., ", ," or ",," -> ",")
        cleaned = re.sub(r',(\s*,)+', ',', cleaned)
        # 3. Clean up any duplicate spaces left behind
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
        return cleaned

    def save(self):
        """Saves current state of dictionary to file."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.dictionary, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving vocabulary: {e}", file=sys.stderr)
            return False
