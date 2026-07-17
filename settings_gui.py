import os
import sys
import json
from i18n import _t

# Fallback check for customtkinter dependency
try:
    import customtkinter as ctk
except ImportError:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Mangler afhængigheder / Dependencies Missing",
        "customtkinter er ikke installeret.\nKør venligst './install.sh' først for at installere alle afhængigheder i det virtuelle miljø."
    )
    sys.exit(1)

# Set theme and styling
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_PATH = "config.json"
VOCAB_PATH = "vocabulary.json"

class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title="", expanded=False, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.title = title
        self.expanded = expanded
        
        # Header frame for the toggle button
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=5, pady=5)
        
        self.toggle_btn = ctk.CTkButton(
            self.header_frame, 
            text="▼ " + self.title if self.expanded else "▶ " + self.title,
            anchor="w",
            fg_color="transparent",
            hover_color=("#dbdbdb", "#2b2b2b"),
            text_color=("#000000", "#ffffff"),
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.toggle
        )
        self.toggle_btn.pack(fill="x", expand=True)
        
        # Content container
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.expanded:
            self.content_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            
    def toggle(self):
        if self.expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.configure(text="▶ " + self.title)
            self.expanded = False
        else:
            self.content_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.toggle_btn.configure(text="▼ " + self.title)
            self.expanded = True

class Speech2AI2TextSettingsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title(_t("window_title"))
        self.geometry("800x700")
        self.minsize(700, 600)
        self.resizable(True, True)
        
        # Load data
        self.config = self.load_json(CONFIG_PATH, {
            "selected_engine": "gemini_cloud",
            "rewrite_locally": False,
            "local_llm_model": "llama3",
            "local_whisper_path": "/usr/bin/whisper",
            "local_model_path": "",
            "groq_api_key": "",
            "gemini_api_key": "",
            "gemini_model": "gemini-3.5-flash",
            "enable_notifications": True,
            "enable_beeps": True,
            "beep_volume": 0.2,
            "enable_gui_overlay": True,
            "shortcut_direct": "<Super>y",
            "shortcut_ai": "<Super><Shift>y",
            "shortcut_ai_prompt": "<Super><Control>y"
        })
        self.vocab = self.load_json(VOCAB_PATH, {
            "pimplify": "PIMplify",
            "git hub": "GitHub",
            "æpi": "API",
            "antigravity": "Antigravity",
            "nocoffee": "NoCoffee",
            "cursor": "Cursor"
        })
        
        # Create UI
        self.create_widgets()

    def load_json(self, path, default_val):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default_val

    def save_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving file {path}: {e}")
            return False

    def create_widgets(self):
        # Create Tabview - filling the main window responsively
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.tabview.add(_t("tab_cloud"))
        self.tabview.add(_t("tab_local"))
        self.tabview.add(_t("tab_system"))
        self.tabview.add(_t("tab_vocab"))
        self.tabview.add(_t("tab_prompts"))
        
        self.setup_engines_tab()
        self.setup_local_models_tab()
        self.setup_system_shortcuts_tab()
        self.setup_vocab_tab()
        self.setup_prompts_tab()

    def add_save_button(self, scroll_frame):
        btn_save = ctk.CTkButton(
            scroll_frame, 
            text=_t("btn_save"), 
            command=self.save_settings, 
            height=40, 
            font=ctk.CTkFont(weight="bold")
        )
        btn_save.pack(fill="x", pady=(20, 10))

    def setup_engines_tab(self):
        tab = self.tabview.tab(_t("tab_cloud"))
        
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Engine selection
        lbl_engine = ctk.CTkLabel(scroll_frame, text=_t("speech_engine_lbl"), font=ctk.CTkFont(size=14, weight="bold"))
        lbl_engine.pack(anchor="w", pady=(10, 5))
        
        self.engine_var = ctk.StringVar(value=self.config.get("selected_engine", "gemini_cloud"))
        engine_dropdown = ctk.CTkOptionMenu(
            scroll_frame, 
            values=["gemini_cloud", "groq_cloud", "local_whisper"],
            variable=self.engine_var,
            width=250
        )
        engine_dropdown.pack(anchor="w", pady=(0, 20))
        
        # Gemini API Settings (Collapsible)
        is_gemini = self.engine_var.get() == "gemini_cloud"
        gemini_cf = CollapsibleFrame(scroll_frame, title=_t("gemini_title"), expanded=is_gemini)
        gemini_cf.pack(fill="x", pady=10)
        
        self.gemini_key_entry = ctk.CTkEntry(gemini_cf.content_frame, placeholder_text=_t("gemini_key_placeholder"), width=500, show="*")
        self.gemini_key_entry.insert(0, self.config.get("gemini_api_key", ""))
        self.gemini_key_entry.pack(anchor="w", fill="x", padx=10, pady=5)
        
        self.gemini_model_entry = ctk.CTkEntry(gemini_cf.content_frame, placeholder_text=_t("gemini_model_placeholder"), width=250)
        self.gemini_model_entry.insert(0, self.config.get("gemini_model", "gemini-3.5-flash"))
        self.gemini_model_entry.pack(anchor="w", padx=10, pady=(5, 10))

        # Groq API Settings (Collapsible)
        is_groq = self.engine_var.get() == "groq_cloud"
        groq_cf = CollapsibleFrame(scroll_frame, title=_t("groq_title"), expanded=is_groq)
        groq_cf.pack(fill="x", pady=10)
        
        self.groq_key_entry = ctk.CTkEntry(groq_cf.content_frame, placeholder_text=_t("groq_key_placeholder"), width=500, show="*")
        self.groq_key_entry.insert(0, self.config.get("groq_api_key", ""))
        self.groq_key_entry.pack(anchor="w", fill="x", padx=10, pady=5)

        self.groq_model_entry = ctk.CTkEntry(groq_cf.content_frame, placeholder_text=_t("groq_model_placeholder"), width=250)
        self.groq_model_entry.insert(0, self.config.get("groq_model", "llama-3.1-8b-instant"))
        self.groq_model_entry.pack(anchor="w", padx=10, pady=(5, 10))

        self.add_save_button(scroll_frame)

    def setup_local_models_tab(self):
        tab = self.tabview.tab(_t("tab_local"))
        
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Ollama Configuration (Collapsible)
        is_ollama_active = self.config.get("rewrite_locally", False)
        ollama_cf = CollapsibleFrame(scroll_frame, title=_t("ollama_title"), expanded=is_ollama_active)
        ollama_cf.pack(fill="x", pady=10)
        
        self.rewrite_local_var = ctk.BooleanVar(value=is_ollama_active)
        chk_rewrite_local = ctk.CTkSwitch(
            ollama_cf.content_frame, 
            text=_t("ollama_switch"),
            variable=self.rewrite_local_var
        )
        chk_rewrite_local.pack(anchor="w", padx=10, pady=10)
        
        self.ollama_model_entry = ctk.CTkEntry(ollama_cf.content_frame, placeholder_text=_t("ollama_model_placeholder"), width=250)
        self.ollama_model_entry.insert(0, self.config.get("local_llm_model", "llama3"))
        self.ollama_model_entry.pack(anchor="w", padx=10, pady=5)

        self.ollama_url_entry = ctk.CTkEntry(ollama_cf.content_frame, placeholder_text=_t("ollama_url_placeholder"), width=500)
        self.ollama_url_entry.insert(0, self.config.get("ollama_api_url", "http://localhost:11434"))
        self.ollama_url_entry.pack(anchor="w", fill="x", padx=10, pady=(5, 10))

        # Local Whisper Settings (Collapsible)
        is_whisper = self.engine_var.get() == "local_whisper"
        whisper_cf = CollapsibleFrame(scroll_frame, title=_t("whisper_title"), expanded=is_whisper)
        whisper_cf.pack(fill="x", pady=10)
        
        self.whisper_path_entry = ctk.CTkEntry(whisper_cf.content_frame, placeholder_text=_t("whisper_path_placeholder"), width=500)
        self.whisper_path_entry.insert(0, self.config.get("local_whisper_path", "/usr/bin/whisper"))
        self.whisper_path_entry.pack(anchor="w", fill="x", padx=10, pady=5)
        
        self.whisper_model_entry = ctk.CTkEntry(whisper_cf.content_frame, placeholder_text=_t("whisper_model_placeholder"), width=500)
        self.whisper_model_entry.insert(0, self.config.get("local_model_path", ""))
        self.whisper_model_entry.pack(anchor="w", fill="x", padx=10, pady=(5, 10))

        self.add_save_button(scroll_frame)

    def setup_system_shortcuts_tab(self):
        tab = self.tabview.tab(_t("tab_system"))
        
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Feedback & notifications
        lbl_feedback = ctk.CTkLabel(scroll_frame, text=_t("feedback_title"), font=ctk.CTkFont(size=14, weight="bold"))
        lbl_feedback.pack(anchor="w", pady=(10, 5))
        
        self.notify_var = ctk.BooleanVar(value=self.config.get("enable_notifications", True))
        chk_notify = ctk.CTkSwitch(scroll_frame, text=_t("chk_notify"), variable=self.notify_var)
        chk_notify.pack(anchor="w", pady=5)
        
        self.beep_var = ctk.BooleanVar(value=self.config.get("enable_beeps", True))
        chk_beep = ctk.CTkSwitch(scroll_frame, text=_t("chk_beep"), variable=self.beep_var)
        chk_beep.pack(anchor="w", pady=5)
        
        self.overlay_var = ctk.BooleanVar(value=self.config.get("enable_gui_overlay", True))
        chk_overlay = ctk.CTkSwitch(scroll_frame, text=_t("chk_overlay"), variable=self.overlay_var)
        chk_overlay.pack(anchor="w", pady=5)
        
        lbl_vol = ctk.CTkLabel(scroll_frame, text=_t("beep_vol_lbl"))
        lbl_vol.pack(anchor="w", pady=(5, 0))
        
        self.vol_slider = ctk.CTkSlider(scroll_frame, from_=0.0, to=1.0, width=200)
        self.vol_slider.set(self.config.get("beep_volume", 0.2))
        self.vol_slider.pack(anchor="w", pady=(0, 20))

        # Advanced settings
        lbl_advanced = ctk.CTkLabel(scroll_frame, text=_t("advanced_title"), font=ctk.CTkFont(size=14, weight="bold"))
        lbl_advanced.pack(anchor="w", pady=(10, 5))
        
        lbl_max_time = ctk.CTkLabel(scroll_frame, text=_t("max_time_lbl"))
        lbl_max_time.pack(anchor="w", pady=(5, 0))
        self.max_time_entry = ctk.CTkEntry(scroll_frame, placeholder_text=_t("max_time_placeholder"), width=250)
        self.max_time_entry.insert(0, str(self.config.get("max_recording_time", 30)))
        self.max_time_entry.pack(anchor="w", pady=(5, 20))

        # Language Settings
        lbl_lang = ctk.CTkLabel(scroll_frame, text=_t("lang_lbl"), font=ctk.CTkFont(size=12, weight="bold"))
        lbl_lang.pack(anchor="w", pady=(5, 0))
        self.lang_var = ctk.StringVar(value=self.config.get("language", "da"))
        self.lang_dropdown = ctk.CTkOptionMenu(
            scroll_frame, 
            values=["da", "en", "es"],
            variable=self.lang_var,
            width=150
        )
        self.lang_dropdown.pack(anchor="w", pady=(5, 20))

        # Tastaturgenveje (Global Keybindings in Cinnamon) (Collapsible)
        shortcuts_cf = CollapsibleFrame(scroll_frame, title=_t("shortcuts_title"), expanded=False)
        shortcuts_cf.pack(fill="x", pady=10)
        
        lbl_sh_desc = ctk.CTkLabel(
            shortcuts_cf.content_frame, 
            text=_t("shortcuts_desc"), 
            text_color="gray",
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        lbl_sh_desc.pack(anchor="w", padx=10, pady=5)
        
        lbl_sh_direct = ctk.CTkLabel(shortcuts_cf.content_frame, text=_t("sh_direct_lbl"))
        lbl_sh_direct.pack(anchor="w", padx=10, pady=(5, 0))
        self.sh_direct_entry = ctk.CTkEntry(shortcuts_cf.content_frame, placeholder_text=_t("sh_direct_placeholder"), width=250)
        self.sh_direct_entry.insert(0, self.config.get("shortcut_direct", "<Super>y"))
        self.sh_direct_entry.pack(anchor="w", padx=10, pady=5)
        
        lbl_sh_ai = ctk.CTkLabel(shortcuts_cf.content_frame, text=_t("sh_ai_lbl"))
        lbl_sh_ai.pack(anchor="w", padx=10, pady=(5, 0))
        self.sh_ai_entry = ctk.CTkEntry(shortcuts_cf.content_frame, placeholder_text=_t("sh_ai_placeholder"), width=250)
        self.sh_ai_entry.insert(0, self.config.get("shortcut_ai", "<Super><Shift>y"))
        self.sh_ai_entry.pack(anchor="w", padx=10, pady=5)

        lbl_sh_ai_prompt = ctk.CTkLabel(shortcuts_cf.content_frame, text=_t("sh_ai_prompt_lbl"))
        lbl_sh_ai_prompt.pack(anchor="w", padx=10, pady=(5, 0))
        self.sh_ai_prompt_entry = ctk.CTkEntry(shortcuts_cf.content_frame, placeholder_text=_t("sh_ai_prompt_placeholder"), width=250)
        self.sh_ai_prompt_entry.insert(0, self.config.get("shortcut_ai_prompt", "<Super><Control>y"))
        self.sh_ai_prompt_entry.pack(anchor="w", padx=10, pady=(5, 15))

        self.add_save_button(scroll_frame)

    def setup_vocab_tab(self):
        tab = self.tabview.tab(_t("tab_vocab"))
        
        # Upper area: Add new replacement
        add_frame = ctk.CTkFrame(tab, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        self.spoken_entry = ctk.CTkEntry(add_frame, placeholder_text=_t("vocab_spoken_placeholder"), width=220)
        self.spoken_entry.pack(side="left", padx=5)
        
        lbl_arrow = ctk.CTkLabel(add_frame, text="➔")
        lbl_arrow.pack(side="left", padx=5)
        
        self.written_entry = ctk.CTkEntry(add_frame, placeholder_text=_t("vocab_written_placeholder"), width=220)
        self.written_entry.pack(side="left", padx=5)
        
        btn_add = ctk.CTkButton(add_frame, text=_t("vocab_btn_add"), width=120, command=self.add_vocab_item)
        btn_add.pack(side="left", padx=5)
        
        # Search field
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text=_t("vocab_search_placeholder"), width=460)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda event: self.filter_vocab_list())
        
        # Lower area: Vocabulary mapping list
        self.vocab_scroll = ctk.CTkScrollableFrame(tab, width=680, height=400)
        self.vocab_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.refresh_vocab_list()

    def refresh_vocab_list(self, filter_text=""):
        # Clear frame widgets
        for widget in self.vocab_scroll.winfo_children():
            widget.destroy()
            
        # Filter and sort keys
        keys = sorted(self.vocab.keys())
        
        row = 0
        for k in keys:
            v = self.vocab[k]
            
            # Skip if filter does not match either key or value
            if filter_text and filter_text.lower() not in k.lower() and filter_text.lower() not in v.lower():
                continue
                
            # Row container
            row_frame = ctk.CTkFrame(self.vocab_scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=2, padx=5)
            
            lbl_key = ctk.CTkLabel(row_frame, text=k, width=250, anchor="w", font=ctk.CTkFont(size=13))
            lbl_key.pack(side="left", padx=5)
            
            lbl_arrow = ctk.CTkLabel(row_frame, text="➔", width=30)
            lbl_arrow.pack(side="left", padx=5)
            
            lbl_val = ctk.CTkLabel(row_frame, text=v, width=250, anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
            lbl_val.pack(side="left", padx=5)
            
            # Delete button (using lambda to capture correct key)
            btn_del = ctk.CTkButton(
                row_frame, 
                text=_t("vocab_btn_delete"), 
                fg_color="#cf4242", 
                hover_color="#b83232", 
                width=60, 
                command=lambda k_val=k: self.delete_vocab_item(k_val)
            )
            btn_del.pack(side="right", padx=5)
            
            row += 1
            
        if row == 0:
            lbl_empty = ctk.CTkLabel(self.vocab_scroll, text=_t("vocab_empty"), text_color="gray")
            lbl_empty.pack(pady=20)

    def filter_vocab_list(self):
        query = self.search_entry.get()
        self.refresh_vocab_list(filter_text=query)

    def setup_prompts_tab(self):
        tab = self.tabview.tab(_t("tab_prompts"))
        
        # Scrollable container for Prompts to ensure responsiveness
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        lbl_info = ctk.CTkLabel(
            scroll_frame, 
            text=_t("prompts_desc"),
            font=ctk.CTkFont(size=13, slant="italic")
        )
        lbl_info.pack(anchor="w", padx=15, pady=(15, 10))
        
        # AI Diktat Prompt
        lbl_ai = ctk.CTkLabel(
            scroll_frame, 
            text=_t("prompt_ai_lbl"), 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_ai.pack(anchor="w", padx=15, pady=(10, 2))
        
        self.prompt_ai_text = ctk.CTkTextbox(scroll_frame, height=160)
        self.prompt_ai_text.pack(fill="x", expand=True, padx=15, pady=(0, 10))
        
        # Load existing or default
        default_prompt_ai = (
            "You are a professional editor. Clean up the following spoken transcription. "
            "Fix grammatical errors, remove stutters, filler words, and clean up sentence structure. "
            "Keep the language of the original text (Danish or English). "
            "Output ONLY the cleaned text."
        )
        self.prompt_ai_text.insert("1.0", self.config.get("prompt_ai", default_prompt_ai))
        
        # AI Coding Prompt
        lbl_ai_prompt = ctk.CTkLabel(
            scroll_frame, 
            text=_t("prompt_ai_prompt_lbl"), 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_ai_prompt.pack(anchor="w", padx=15, pady=(10, 2))
        
        self.prompt_ai_prompt_text = ctk.CTkTextbox(scroll_frame, height=160)
        self.prompt_ai_prompt_text.pack(fill="x", expand=True, padx=15, pady=(0, 15))
        
        default_prompt_ai_prompt = (
            "You are an expert technical director. Translate the following spoken Danish/English description "
            "into a highly precise, structured, and action-oriented prompt for an AI coding agent (like Cursor or Antigravity). "
            "Focus on strict technical requirements, libraries, and clean architecture. "
            "Output ONLY the final prompt. No conversational filler or markdown code blocks."
        )
        self.prompt_ai_prompt_text.insert("1.0", self.config.get("prompt_ai_prompt", default_prompt_ai_prompt))

    def add_vocab_item(self):
        spoken = self.spoken_entry.get().strip().lower()
        written = self.written_entry.get().strip()
        
        if not spoken or not written:
            # Simple error dialog
            self.show_status_window(_t("status_error_dialog"), _t("status_vocab_fill_fields"))
            return
            
        self.vocab[spoken] = written
        if self.save_json(VOCAB_PATH, self.vocab):
            self.spoken_entry.delete(0, "end")
            self.written_entry.delete(0, "end")
            self.search_entry.delete(0, "end")
            self.refresh_vocab_list()
            self.show_status_window(_t("status_success"), f"{_t('status_vocab_added')} '{spoken}' ➔ '{written}'")
            
    def delete_vocab_item(self, key):
        if key in self.vocab:
            del self.vocab[key]
            if self.save_json(VOCAB_PATH, self.vocab):
                self.filter_vocab_list()
                self.show_status_window(_t("status_success"), f"{_t('status_vocab_deleted')} '{key}'")
    def save_settings(self):
        self.config["selected_engine"] = self.engine_var.get()
        self.config["gemini_api_key"] = self.gemini_key_entry.get().strip()
        self.config["gemini_model"] = self.gemini_model_entry.get().strip()
        self.config["groq_api_key"] = self.groq_key_entry.get().strip()
        self.config["rewrite_locally"] = self.rewrite_local_var.get()
        self.config["local_llm_model"] = self.ollama_model_entry.get().strip()
        self.config["local_whisper_path"] = self.whisper_path_entry.get().strip()
        self.config["local_model_path"] = self.whisper_model_entry.get().strip()
        self.config["enable_notifications"] = self.notify_var.get()
        self.config["enable_beeps"] = self.beep_var.get()
        self.config["beep_volume"] = float(round(self.vol_slider.get(), 2))
        self.config["enable_gui_overlay"] = self.overlay_var.get()
        self.config["language"] = self.lang_var.get()
        
        # Save custom prompts
        self.config["prompt_ai"] = self.prompt_ai_text.get("1.0", "end-1c").strip()
        self.config["prompt_ai_prompt"] = self.prompt_ai_prompt_text.get("1.0", "end-1c").strip()
        
        # Save advanced settings
        try:
            self.config["max_recording_time"] = int(self.max_time_entry.get().strip() or 30)
        except Exception:
            self.config["max_recording_time"] = 30
        self.config["ollama_api_url"] = self.ollama_url_entry.get().strip() or "http://localhost:11434"
        self.config["groq_model"] = self.groq_model_entry.get().strip() or "llama-3.1-8b-instant"
        
        new_shortcut_direct = self.sh_direct_entry.get().strip()
        new_shortcut_ai = self.sh_ai_entry.get().strip()
        new_shortcut_ai_prompt = self.sh_ai_prompt_entry.get().strip()
        
        self.config["shortcut_direct"] = new_shortcut_direct
        self.config["shortcut_ai"] = new_shortcut_ai
        self.config["shortcut_ai_prompt"] = new_shortcut_ai_prompt
        
        # Save to Cinnamon custom keybindings database
        self.set_cinnamon_shortcut("direct", new_shortcut_direct)
        self.set_cinnamon_shortcut("ai", new_shortcut_ai)
        self.set_cinnamon_shortcut("ai_prompt", new_shortcut_ai_prompt)
        
        if self.save_json(CONFIG_PATH, self.config):
            self.show_status_window(_t("status_success"), _t("status_saved"))

    def get_cinnamon_custom_shortcuts(self):
        import subprocess, re
        try:
            out = subprocess.check_output(["dconf", "read", "/org/cinnamon/desktop/keybindings/custom-list"], text=True).strip()
            out_clean = out.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace("@as", "")
            custom_ids = [x.strip() for x in out_clean.split(",") if x.strip() and x.strip() != "__dummy__"]
            
            shortcuts = []
            for cid in custom_ids:
                try:
                    name = subprocess.check_output(["dconf", "read", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{cid}/name"], text=True).strip().strip("'\"")
                    command = subprocess.check_output(["dconf", "read", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{cid}/command"], text=True).strip().strip("'\"")
                    binding = subprocess.check_output(["dconf", "read", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{cid}/binding"], text=True).strip()
                    match = re.search(r"'(.*?)'", binding)
                    bind_val = match.group(1) if match else ""
                    shortcuts.append({"id": cid, "name": name, "command": command, "binding": bind_val})
                except Exception:
                    continue
            return shortcuts
        except Exception:
            return []

    def set_cinnamon_shortcut(self, mode, binding):
        import subprocess, os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        python_path = os.path.join(script_dir, ".venv/bin/python")
        main_path = os.path.join(script_dir, "main.py")
        target_command = f"{python_path} {main_path} {mode}"
        if mode == "direct":
            target_name = "Speech2AI2Text Diktat"
        elif mode == "ai":
            target_name = "Speech2AI2Text AI Diktat (Grammatik)"
        else:
            target_name = "Speech2AI2Text AI Prompt"
        
        try:
            out = subprocess.check_output(["dconf", "read", "/org/cinnamon/desktop/keybindings/custom-list"], text=True).strip()
        except Exception:
            out = "@as []"
            
        out_clean = out.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace("@as", "")
        custom_ids = [x.strip() for x in out_clean.split(",") if x.strip() and x.strip() != "__dummy__"]
        
        existing_cid = None
        shortcuts = self.get_cinnamon_custom_shortcuts()
        for s in shortcuts:
            if s["command"] == target_command or (main_path in s["command"] and mode in s["command"]):
                existing_cid = s["id"]
                break
                
        binding_val = f"['{binding}']" if binding else "[]"
                
        if existing_cid:
            subprocess.run(["dconf", "write", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{existing_cid}/binding", binding_val])
            subprocess.run(["dconf", "write", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{existing_cid}/command", f"'{target_command}'"])
        elif binding:
            i = 0
            while True:
                cid = f"custom{i}"
                if cid not in custom_ids:
                    break
                i += 1
            custom_ids.append(cid)
            list_str = "[" + ", ".join(f"'{x}'" for x in custom_ids) + ", '__dummy__']"
            
            subprocess.run(["dconf", "write", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{cid}/name", f"'{target_name}'"])
            subprocess.run(["dconf", "write", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{cid}/command", f"'{target_command}'"])
            subprocess.run(["dconf", "write", f"/org/cinnamon/desktop/keybindings/custom-keybindings/{cid}/binding", binding_val])
            subprocess.run(["dconf", "write", "/org/cinnamon/desktop/keybindings/custom-list", list_str])

    def show_status_window(self, title, message):
        """Displays a clean status overlay window that fades out or can be closed."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("350x120")
        dialog.transient(self) # Keep on top of main window
        dialog.resizable(False, False)
        
        # Center dialog relative to main window
        x = self.winfo_x() + (self.winfo_width() // 2) - 175
        y = self.winfo_y() + (self.winfo_height() // 2) - 60
        dialog.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(dialog, text=message, wraplength=300, font=ctk.CTkFont(size=12))
        lbl.pack(pady=20)
        
        btn = ctk.CTkButton(dialog, text="OK", width=80, command=dialog.destroy)
        btn.pack(pady=(0, 10))

if __name__ == "__main__":
    # Change working directory to the directory of this script to locate JSON files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    app = Speech2AI2TextSettingsApp()
    app.mainloop()
