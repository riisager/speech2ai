# speech2ai - AI-Powered Voice Dictation for Linux (Mint/Cinnamon)

[Dansk version nedenfor](#danish)

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

---

<a name="danish"></a>

# speech2ai - AI-Powered Voice Dictation for Linux (Mint/Cinnamon)

**speech2ai** er et åbent og yderst optimeret system til stemme-diktering på Linux (specifikt bygget til Linux Mint/Cinnamon og X11-skrivebordsmiljøer). Programmet lader dig diktere tekst direkte ind i ethvert aktivt tekstfelt (webbrowsere, teksteditorer, terminaler) ved hjælp af globale genvejstaster.

Systemet understøtter både direkte ordret transkription og avanceret AI-redigering, herunder automatisk grammatikretning og generering af strukturerede prompter til kodningsagenter (f.eks. Cursor eller Antigravity).

---

## ✨ Nøglefunktioner

*   **Lynhurtig indlæsning (<100ms):** Takket være doven indlæsning (lazy-loading) af tunge lydbiblioteker reagerer det visuelle overlay øjeblikkeligt, når du trykker på din genvejstast.
*   **3 smarte dikteringstilstande:**
    1.  **Almindelig Diktat:** Transkriberer ordret præcis hvad du siger uden AI-indblanding.
    2.  **AI Diktat (Grammatik):** Transkriberer din tale og bruger AI til at fjerne stammende ord, fyldord (som *øh, øhm, ah*) og rette grammatik/sætningsstruktur, mens sproget bevares.
    3.  **AI Prompt (Kodetilstand):** Oversætter dine talte instruktioner til en yderst præcis, struktureret og handlingsorienteret prompt til AI-kodningsværktøjer.
*   **Visuelt Overlay (iOS-stil):** En flot, flydende kapsel i bunden af skærmen med realtid-lydbølgevisualisering, der viser programmets status.
*   **Indbygget sproglag (i18n):** Fuld understøttelse af **engelsk**, **dansk** og **spansk**. Standardsproget er engelsk, men kan let ændres direkte i indstillingerne.
*   **Personlig Ordbog:** Indbygget ordbog til lyd-korrektioner, så svære eller udtalte ord automatisk rettes (f.eks. *æpi* ➔ *API*, *git hub* ➔ *GitHub*).
*   **Automatisk Mint/Cinnamon integration:** Nem opsætning af globale tastaturgenveje direkte fra programmets grafiske indstillinger, som synkroniseres direkte med Linux Mints `dconf`-system.
*   **Systembakke (Tray App):** Et diskret mikrofon-ikon ved uret, hvorfra du nemt kan starte optagelser eller åbne indstillingspanelet.

---

## 🛠️ Installation

Følg disse enkle trin for at installere **speech2ai**:

1.  Åbn din terminal i projektmappen.
2.  Kør installationsscriptet:
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    *Installationsscriptet vil undersøge om du mangler nødvendige systempakker (`xclip`, `xdotool`, `portaudio` m.m.), og tilbyde at installere dem automatisk for dig via `apt`.*
3.  Genstart din computer eller log ud/ind for at aktivere genveje og autostart af tray-ikonet.

---

## ⚙️ Opsætning af Tastaturgenveje

Efter installationen kan du søge efter **Speech2AI Indstillinger** i din startmenu for at indtaste din Gemini/Groq API-nøgle og ændre dine genveje.

Programmet understøtter følgende tre genveje som standard:
*   **Almindelig Diktat:** `Super + Y`
*   **AI Diktat (Grammatik):** `Super + Shift + Y`
*   **AI Prompt (Agent-kode):** `Super + Ctrl + Y`

Du kan ændre disse inde i indstillingsvinduet, og programmet vil automatisk registrere dem i Linux Mint.
