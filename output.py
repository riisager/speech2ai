import sys
from system_compat import PlatformCompat

class ClipboardPaster:
    """High-level clipboard and text injection interface."""

    @staticmethod
    def paste(text):
        """Pastes the text into the active field and leaves it in the clipboard permanently."""
        PlatformCompat.paste_text(text)

    @staticmethod
    def get_selected_text():
        """Captures the active highlighted/selected text instantly with zero unnecessary delays."""
        return PlatformCompat.get_selected_text()
