import os
import sys
import time
import threading
import math
import tkinter as tk
import customtkinter as ctk

from audio_capture import AudioRecorder
from dictionary import CustomDictionary
from rewrite import RewriteEngine
from output import ClipboardPaster
from system_compat import PlatformCompat
from main import create_resilient_session, prewarm_connection, transcribe_gemini, transcribe_groq, transcribe_local_whisper
from i18n import _t

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

WINDOW_WIDTH = 430
WINDOW_HEIGHT = 68
CAPSULE_BG = "#161618"
TEXT_COLOR = "#f3f3f3"
ACCENT_RED = "#ff3b30"
ACCENT_BLUE = "#007aff"
ACCENT_GREEN = "#34c759"
ACCENT_PURPLE = "#8e44ad"
ACCENT_ORANGE = "#e67e22"

class RecordingOverlay(ctk.CTk):
    def __init__(self, mode="direct", config=None, run_pipeline_callback=None, persistent=False):
        super().__init__()
        self.persistent = persistent
        self.is_destroyed = False
        
        self.mode = mode.upper()
        self.config = config or {}
        self.run_pipeline_callback = run_pipeline_callback
        
        # Configure window properties
        self.title("Speech2AI Overlay")
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.95)
        self.configure(fg_color=CAPSULE_BG)
        
        # Frameless splash style
        if not PlatformCompat.is_wayland():
            try:
                self.attributes("-type", "splash")
            except Exception:
                self.overrideredirect(True)
        else:
            self.overrideredirect(True)
        
        # Center at top/bottom of screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - WINDOW_WIDTH) // 2
        y = screen_height - WINDOW_HEIGHT - 85
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        
        self.app_state = "recording"
        self.status_text = _t("state_recording")
        
        self.num_bars = 9
        self.bar_heights = [4.0] * self.num_bars
        self.max_bar_height = 25
        
        self.create_widgets()
        self.bind_events()
        self.update_visuals()

    def bind_events(self):
        """Binds keyboard controls for instant user cancellation/stopping."""
        self.bind("<Escape>", lambda e: self.cancel_recording())
        self.bind("<space>", lambda e: self.stop_recording())
        self.bind("<Return>", lambda e: self.stop_recording())

    def destroy(self):
        self.is_destroyed = True
        if self.persistent:
            self.withdraw()
        else:
            os._exit(0)

    def update_mode(self, mode):
        self.mode = mode.upper()
        if self.mode == "DIRECT":
            display_mode = _t("badge_direct")
            badge_color = ACCENT_BLUE
        elif self.mode == "AI":
            display_mode = _t("badge_ai")
            badge_color = ACCENT_PURPLE
        else:
            display_mode = _t("badge_prompt")
            badge_color = ACCENT_ORANGE
            
        self.badge_frame.configure(fg_color=badge_color)
        self.badge_label.configure(text=display_mode)

    def show(self, mode, initial_keys=None):
        self.is_destroyed = False
        self.app_state = "recording"
        self.status_text = _t("state_recording")
        self.status_label.configure(text=self.status_text)
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - WINDOW_WIDTH) // 2
        y = screen_height - WINDOW_HEIGHT - 85
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        
        self.capsule.configure(border_color="#2c2c2e")
        self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_RED)
        self.bar_heights = [4.0] * self.num_bars
        
        self.update_mode(mode)
        AudioRecorder.reset_events()
        
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        
        self.led_flash_state = True
        self.flash_led()

    def create_widgets(self):
        self.capsule = ctk.CTkFrame(
            self, 
            width=WINDOW_WIDTH, 
            height=WINDOW_HEIGHT, 
            corner_radius=22,
            fg_color=CAPSULE_BG,
            border_width=1.5,
            border_color="#2c2c2e"
        )
        self.capsule.pack(fill="both", expand=True)
        self.capsule.pack_propagate(False)
        
        # 1. State indicator LED
        self.led_canvas = tk.Canvas(self.capsule, width=20, height=20, bg=CAPSULE_BG, highlightthickness=0)
        self.led_canvas.pack(side="left", padx=(20, 10))
        self.led_circle = self.led_canvas.create_oval(3, 3, 17, 17, fill=ACCENT_RED, outline="")
        self.led_flash_state = True
        self.flash_led()

        # 2. Status text label
        self.status_label = ctk.CTkLabel(
            self.capsule, 
            text=self.status_text, 
            text_color=TEXT_COLOR,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status_label.pack(side="left", padx=10)

        # 3. Mode Badge
        if self.mode == "DIRECT":
            display_mode = _t("badge_direct")
            badge_color = ACCENT_BLUE
        elif self.mode == "AI":
            display_mode = _t("badge_ai")
            badge_color = ACCENT_PURPLE
        else:
            display_mode = _t("badge_prompt")
            badge_color = ACCENT_ORANGE
            
        self.badge_frame = ctk.CTkFrame(
            self.capsule, 
            fg_color=badge_color, 
            corner_radius=10, 
            height=20
        )
        self.badge_frame.pack(side="right", padx=(10, 20))
        
        self.badge_label = ctk.CTkLabel(
            self.badge_frame, 
            text=display_mode, 
            text_color="#ffffff",
            font=ctk.CTkFont(size=10, weight="bold"),
            padx=8,
            pady=2
        )
        self.badge_label.pack()

        # 4. Waveform Canvas
        self.wave_canvas = tk.Canvas(self.capsule, width=90, height=35, bg=CAPSULE_BG, highlightthickness=0)
        self.wave_canvas.pack(side="right", padx=10)
        
        # Click to stop on all components
        for widget in [self.capsule, self.status_label, self.led_canvas, self.wave_canvas, self.badge_frame, self.badge_label]:
            widget.bind("<Button-1>", lambda e: self.stop_recording())

    def flash_led(self):
        if getattr(self, "is_destroyed", False):
            return
        if self.app_state == "recording":
            self.led_flash_state = not self.led_flash_state
            color = ACCENT_RED if self.led_flash_state else "#5c1b18"
            try:
                self.led_canvas.itemconfig(self.led_circle, fill=color)
                self.after(350, self.flash_led)
            except Exception:
                pass

    def set_state(self, state, text=None):
        if getattr(self, "is_destroyed", False):
            return
        self.app_state = state
        if text:
            self.status_text = text
            self.status_label.configure(text=text)
            
        if state == "processing":
            self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_BLUE)
            self.capsule.configure(border_color=ACCENT_BLUE)
        elif state == "success":
            self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_GREEN)
            self.capsule.configure(border_color=ACCENT_GREEN)
        elif state == "error":
            self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_RED)
            self.capsule.configure(border_color=ACCENT_RED)

    def stop_recording(self):
        """Stops active recording gracefully."""
        if self.app_state == "recording":
            AudioRecorder.request_stop()

    def cancel_recording(self):
        """Cancels active recording without processing."""
        if self.app_state == "recording":
            AudioRecorder.request_cancel()
            self.set_state("error", _t("state_canceled"))

    def draw_waveform(self):
        if getattr(self, "is_destroyed", False):
            return
        try:
            self.wave_canvas.delete("all")
            width = 90
            height = 35
            center_y = height / 2.0
            
            bar_width = 3.5
            gap = 5.5
            start_x = (width - (self.num_bars * (bar_width + gap) - gap)) / 2.0
            
            for i, h in enumerate(self.bar_heights):
                x = start_x + i * (bar_width + gap)
                y0 = center_y - h / 2.0
                y1 = center_y + h / 2.0
                
                if self.app_state == "recording":
                    fill_color = ACCENT_RED
                elif self.app_state == "processing":
                    fill_color = ACCENT_BLUE
                elif self.app_state == "success":
                    fill_color = ACCENT_GREEN
                else:
                    fill_color = "#555558"
                    
                self.wave_canvas.create_line(x, y0, x, y1, width=bar_width, fill=fill_color, capstyle=tk.ROUND)
        except Exception:
            pass

    def update_visuals(self):
        if getattr(self, "is_destroyed", False):
            return
        try:
            if self.app_state == "recording":
                vol = AudioRecorder.current_volume
                target_height = 4.0 + vol * self.max_bar_height
                
                for i in range(self.num_bars):
                    dist_from_center = abs(i - (self.num_bars // 2))
                    decay = max(0.2, 1.0 - (dist_from_center * 0.22))
                    bar_target = target_height * decay
                    
                    self.bar_heights[i] = self.bar_heights[i] * 0.4 + bar_target * 0.6
                    self.bar_heights[i] = max(4.0, min(self.max_bar_height, self.bar_heights[i]))
                    
            elif self.app_state == "processing":
                t = time.time() * 8.0
                for i in range(self.num_bars):
                    target = (math.sin(t + i * 0.7) + 1.0) / 2.0 * (self.max_bar_height * 0.7)
                    self.bar_heights[i] = self.bar_heights[i] * 0.4 + target * 0.6
                    
            elif self.app_state in ("success", "error"):
                for i in range(self.num_bars):
                    self.bar_heights[i] = self.bar_heights[i] * 0.7 + 2.0 * 0.3
    
            self.draw_waveform()
            self.after(40, self.update_visuals)
        except Exception:
            pass


def start_overlay_pipeline(mode="direct", config=None, overlay=None, initial_keys=None, session=None):
    """Initializes and runs the GUI capsule overlay alongside the dictation pipeline."""
    if session is None:
        session = create_resilient_session()

    # 1. Capture selected text immediately with 0ms artificial sleep
    selected_text = ""
    if mode != "direct":
        selected_text = PlatformCompat.get_selected_text()
        if selected_text:
            print(f"Captured active selection: {len(selected_text)} chars")

    if initial_keys is None:
        initial_keys = PlatformCompat.get_pressed_keys()
            
    is_warm_start = (overlay is not None)
    if overlay is None:
        overlay = RecordingOverlay(mode=mode, config=config, persistent=False)
    else:
        overlay.show(mode, initial_keys)
        
    def thread_target():
        TEMP_WAV_PATH = "/tmp/speech2ai2text_dictation.wav"
        VOCAB_PATH = os.path.join(SCRIPT_DIR, "vocabulary.json")
        LOCK_FILE = "/tmp/speech2ai2text_active.lock"
        
        try:
            with open(LOCK_FILE, "w") as f:
                f.write(mode)
        except Exception:
            pass
            
        try:
            # Parallel TLS pre-warm while user speaks
            prewarm_connection(config, session)

            # 1. Recording Phase
            recorder = AudioRecorder(device_name=config.get("input_device"))
            audio_file = recorder.record(
                max_duration=config.get("max_recording_time", 30), 
                output_path=TEMP_WAV_PATH, 
                enable_beeps=config.get("enable_beeps", True),
                beep_volume=config.get("beep_volume", 0.2),
                initial_keys=initial_keys,
                mode_preference=config.get("recording_mode", "auto")
            )
            
            overlay.set_state("processing", _t("state_processing"))
            
            if not audio_file or not os.path.exists(audio_file):
                overlay.set_state("error", _t("state_canceled"))
                time.sleep(0.8)
                if overlay.persistent:
                    overlay.after(0, overlay.withdraw)
                else:
                    overlay.after(0, overlay.destroy)
                return
                
            # 2. Transcription Phase
            engine = config.get("selected_engine", "gemini_cloud")
            if engine == "gemini_cloud":
                raw_text = transcribe_gemini(audio_file, config, session=session)
            elif engine == "groq_cloud":
                raw_text = transcribe_groq(audio_file, config, session=session)
            elif engine == "local_whisper":
                raw_text = transcribe_local_whisper(audio_file, config)
            else:
                raise ValueError(f"Ukendt motor: {engine}")
                
            if not raw_text.strip():
                overlay.set_state("error", _t("state_nothing_heard"))
                time.sleep(1.0)
                if overlay.persistent:
                    overlay.after(0, overlay.withdraw)
                else:
                    overlay.after(0, overlay.destroy)
                return
                
            # 3. Custom Dictionary
            dictionary = CustomDictionary(filepath=VOCAB_PATH)
            clean_text = dictionary.clean_text(raw_text)
            
            # 4. Rewrite (AI mode)
            if mode == "ai":
                overlay.set_state("processing", _t("state_rewriting"))
                rewriter = RewriteEngine(config, session=session)
                clean_text = rewriter.process(clean_text, style="clean_transcription", selected_text=selected_text)
            elif mode == "ai_prompt":
                overlay.set_state("processing", _t("state_rewriting"))
                rewriter = RewriteEngine(config, session=session)
                clean_text = rewriter.process(clean_text, style="cursor_prompt", selected_text=selected_text)
                
            # 5. Paste & Success State
            overlay.set_state("success", _t("state_inserting"))
            ClipboardPaster.paste(clean_text)
            time.sleep(0.4)
            
        except Exception as e:
            error_str = str(e)
            print(f"Error in overlay pipeline: {error_str}", file=sys.stderr)
            overlay.set_state("error", _t("state_error"))
            time.sleep(1.5)
        finally:
            try:
                if os.path.exists(LOCK_FILE):
                    os.remove(LOCK_FILE)
            except Exception:
                pass
                
            if overlay.persistent:
                overlay.after(0, overlay.withdraw)
            else:
                overlay.after(0, overlay.destroy)

    pipeline_thread = threading.Thread(target=thread_target, daemon=True)
    pipeline_thread.start()
    
    if not is_warm_start:
        overlay.mainloop()

if __name__ == "__main__":
    from main import load_config
    cfg = load_config()
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    start_overlay_pipeline(mode=run_mode, config=cfg)
