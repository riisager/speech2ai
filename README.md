# speech2ai - AI-Powered Voice Dictation for Linux (Mint/Cinnamon)

**speech2ai** is an open-source, highly optimized voice dictation utility designed for Linux desktop environments (optimized for Linux Mint/Cinnamon and X11). It allows you to dictate text directly into any active input field (browsers, text editors, terminals) using global keyboard shortcuts.

The system supports both direct word-for-word transcription and advanced AI rewrite modes, such as grammar correction and structured prompt generation for AI coding agents (e.g., Cursor or Antigravity).

---

## ✨ Features

*   **Ultra-Fast Activation (<100ms):** Leverages lazy-loading for heavy audio libraries so the visual floating overlay appears instantly when you hit your hotkey.
*   **3 Smart Dictation Modes:**
    1.  **Direct Dictation:** Transcribes spoken audio exactly as heard without any AI edits.
    2.  **AI Dictation (Grammar):** Corrects grammar, spelling, and removes stutters or filler words (such as *uh, um, er*) while maintaining the language of the original text.
    3.  **AI Prompt (Coding Agent):** Translates spoken Danish/English description into a precise, action-oriented prompt tailored for AI coding agents.
*   **Floating HUD (iOS-Style):** A sleek capsule overlay at the bottom of the screen with a real-time waveform visualizer showing state and sound volume.
*   **Built-in Localization (i18n):** Full support for **English**, **Danish**, and **Spanish**. The default language is English, and it can be changed directly from the settings GUI.
*   **Custom Vocabulary (Ordbog):** Map mispronounced or technical terms to correct spellings (e.g., *æpi* ➔ *API*, *git hub* ➔ *GitHub*).
*   **Automatic Mint/Cinnamon Integration:** Manage global keyboard shortcuts directly from the settings GUI, syncing programmatically with Linux Mint's `dconf` keybindings registry.
*   **System Tray App:** A clean microphone icon in your tray menu to trigger recording modes or configure settings.

---

## 🛠️ Installation

Set up **speech2ai** by running the automated installation script:

1.  Open your terminal in the cloned directory.
2.  Execute the installer:
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    *The installer checks for system packages (`xclip`, `xdotool`, `portaudio`, etc.) and offers to install them automatically.*
3.  Restart your session (log out and back in) to activate the autostart and shortcut registry.

---

## ⚙️ Keyboard Shortcuts

After installation, search for **Speech2AI Settings** in your start menu to enter your API keys and configure shortcuts.

The application binds the following shortcuts by default:
*   **Direct Dictation:** `Super + Y`
*   **AI Dictation (Grammar):** `Super + Shift + Y`
*   **AI Prompt (Coding):** `Super + Ctrl + Y`

You can change these in the settings interface, and the program will automatically update them in Linux Mint.

---

## ⚖️ License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
