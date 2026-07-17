import os
import sys
import time
import threading
import math
import random
import tkinter as tk
import customtkinter as ctk

from audio_capture import get_pressed_keys, AudioRecorder
from dictionary import CustomDictionary
from rewrite import RewriteEngine
from output import ClipboardPaster
from i18n import _t

# Resolve files relative to this script's directory for portability
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Sane placement defaults
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 65
CAPSULE_BG = "#161618"      # Deep obsidian
TEXT_COLOR = "#f3f3f3"      # Off-white
ACCENT_RED = "#ff3b30"      # iOS style alert red
ACCENT_BLUE = "#007aff"     # iOS style clean blue
ACCENT_GREEN = "#34c759"    # iOS style success green

class RecordingOverlay(ctk.CTk):
    def __init__(self, mode="direct", config=None, run_pipeline_callback=None):
        super().__init__()
        self.is_destroyed = False
        
        self.mode = mode.upper()
        self.config = config or {}
        self.run_pipeline_callback = run_pipeline_callback
        
        # Configure window settings
        self.title("Speech2AI2Text Overlay")
        self.attributes("-topmost", True)  # Always on top
        self.attributes("-alpha", 0.94)    # Semi-transparent glassmorphic look
        self.configure(fg_color=CAPSULE_BG)
        
        # Use splash window type to remove titlebar and borders safely on X11/Cinnamon
        self.attributes("-type", "splash")
        
        # Center in bottom portion of screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - WINDOW_WIDTH) // 2
        y = screen_height - WINDOW_HEIGHT - 85  # Floats nicely above the bottom panel
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        
        # App state
        # "recording", "processing", "success", "error"
        self.app_state = "recording"
        self.status_text = _t("state_recording")
        
        # Visualizer animation states
        self.num_bars = 9
        self.bar_heights = [4.0] * self.num_bars
        self.max_bar_height = 25
        
        self.create_widgets()
        
        # Start visualization loop
        self.update_visuals()

    def destroy(self):
        """Forces clean termination of the process when the window is destroyed
        to release the singleton file locks immediately.
        """
        self.is_destroyed = True
        import os
        os._exit(0)

    def create_widgets(self):
        # Outer capsule container frame
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
        
        # 1. State indicator LED (flashing red circle)
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

        # 3. Mode Badge (DIRECT, AI or AI_PROMPT)
        if self.mode == "DIRECT":
            display_mode = _t("badge_direct")
            badge_color = ACCENT_BLUE
        elif self.mode == "AI":
            display_mode = _t("badge_ai")
            badge_color = "#8e44ad"
        else:
            display_mode = _t("badge_prompt")
            badge_color = "#e67e22" # Premium orange/gold
            
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

        # 4. Waveform Canvas visualizer (sits in the middle)
        self.wave_canvas = tk.Canvas(self.capsule, width=90, height=35, bg=CAPSULE_BG, highlightthickness=0)
        self.wave_canvas.pack(side="right", padx=10)
        
        # Bind click to stop recording on all widgets
        for widget in [self.capsule, self.status_label, self.led_canvas, self.wave_canvas, self.badge_frame, self.badge_label]:
            widget.bind("<Button-1>", lambda e: self.stop_recording())

    def flash_led(self):
        """Flashes the LED to indicate active recording state."""
        if getattr(self, "is_destroyed", False):
            return
        if self.app_state == "recording":
            color = ACCENT_RED if self.led_flash_state else "#6b1814"
            self.led_canvas.itemconfig(self.led_circle, fill=color)
            self.led_flash_state = not self.led_flash_state
            self.after(500, self.flash_led)
        elif self.app_state == "processing":
            # Yellow-orange color pulsing
            pulsing = int(127 + 127 * math.sin(time.time() * 6))
            color = f"#{pulsing:02x}{pulsing*7//10:02x}00"
            self.led_canvas.itemconfig(self.led_circle, fill=color)
            self.after(100, self.flash_led)
        elif self.app_state == "success":
            self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_GREEN)
        elif self.app_state == "error":
            self.led_canvas.itemconfig(self.led_circle, fill="#888888")

    def set_state(self, state, status_text=None):
        """Sets the state of the overlay (e.g. processing, success) and updates text/animations."""
        self.app_state = state
        if status_text:
            self.status_text = status_text
            self.status_label.configure(text=status_text)
            
        if state == "processing":
            self.led_flash_state = True
            self.flash_led()
        elif state == "success":
            self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_GREEN)
            self.capsule.configure(border_color="#1c5427") # Green border
        elif state == "error":
            self.led_canvas.itemconfig(self.led_circle, fill=ACCENT_RED)
            self.capsule.configure(border_color="#631414") # Dark red border
            
    def stop_recording(self):
        """Signals the background recording thread to stop recording immediately."""
        if self.app_state == "recording":
            AudioRecorder.stop_requested = True

    def draw_waveform(self):
        try:
            if getattr(self, "is_destroyed", False) or not self.winfo_exists():
                return
            self.wave_canvas.delete("all")
            
            canvas_width = 90
            canvas_height = 35
            center_y = canvas_height / 2
            
            spacing = 7
            bar_width = 3.5
            
            start_x = (canvas_width - (self.num_bars * spacing)) / 2
            
            for i in range(self.num_bars):
                h = self.bar_heights[i]
                x = start_x + (i * spacing) + (bar_width / 2)
                
                # Sane bounds check
                h = max(2.0, min(self.max_bar_height, h))
                
                # Draw rounded caps bar
                color = ACCENT_RED if self.app_state == "recording" else (ACCENT_BLUE if self.app_state == "processing" else ACCENT_GREEN)
                self.wave_canvas.create_line(
                    x, center_y - h/2,
                    x, center_y + h/2,
                    fill=color,
                    width=bar_width,
                    capstyle="round"
                )
        except Exception:
            pass

    def update_visuals(self):
        """Updates the visualizer height array every 40ms."""
        try:
            if getattr(self, "is_destroyed", False) or not self.winfo_exists():
                return
            t = time.time()
            
            if self.app_state == "recording":
                # 1. Real-time microphone RMS volume animation
                vol = AudioRecorder.current_volume
                for i in range(self.num_bars):
                    # Introduce random variation to simulate a organic frequency spectrum
                    noise = random.uniform(-0.15, 0.15)
                    factor = max(0.05, min(1.0, (vol + noise)))
                    
                    # Weight middle bars to be taller (bell curve)
                    center_bias = 1.0 - (abs(i - (self.num_bars-1)/2) / ((self.num_bars-1)/2))
                    target = factor * self.max_bar_height * (0.3 + 0.7 * center_bias)
                    
                    # Exponential smoothing filter
                    self.bar_heights[i] = self.bar_heights[i] * 0.35 + target * 0.65
                    
            elif self.app_state == "processing":
                # 2. Sine-wave idle processing animation
                speed = 10
                for i in range(self.num_bars):
                    # Create rolling sine wave
                    target = (math.sin(t * speed + i * 0.8) + 1.0) / 2.0 * (self.max_bar_height * 0.7)
                    self.bar_heights[i] = self.bar_heights[i] * 0.4 + target * 0.6
                    
            elif self.app_state in ("success", "error"):
                # 3. Flatten out the wave
                for i in range(self.num_bars):
                    self.bar_heights[i] = self.bar_heights[i] * 0.7 + 2.0 * 0.3
    
            self.draw_waveform()
            self.after(40, self.update_visuals)
        except Exception:
            pass

def start_overlay_pipeline(mode="direct", config=None):
    """Initializes and runs the GUI capsule overlay alongside the dictation pipeline."""
    # 1. Detect shortcut keys initially pressed on launch on the main thread
    # BEFORE starting Tkinter window mapping or background threads to prevent Xlib deadlocks.
    initial_keys = get_pressed_keys()
    if not initial_keys:
        time.sleep(0.05)
        initial_keys = get_pressed_keys()
        
    overlay = RecordingOverlay(mode=mode, config=config)
    
    # We define the background runner inside a thread so Tkinter mainloop can remain active on main thread
    def thread_target():
        # TEMP files paths
        TEMP_WAV_PATH = "/tmp/speech2ai2text_dictation.wav"
        VOCAB_PATH = os.path.join(SCRIPT_DIR, "vocabulary.json")
        
        LOCK_FILE = "/tmp/speech2ai2text_active.lock"
        try:
            with open(LOCK_FILE, "w") as f:
                f.write(mode)
        except Exception:
            pass
            
        try:
            # 1. Recording Phase
            recorder = AudioRecorder()
            audio_file = recorder.record(
                max_duration=config.get("max_recording_time", 30), 
                output_path=TEMP_WAV_PATH, 
                enable_beeps=config.get("enable_beeps", True),
                beep_volume=config.get("beep_volume", 0.2),
                initial_keys=initial_keys
            )
            
            # Transition to processing state
            overlay.set_state("processing", _t("state_processing"))
            
            if not audio_file or not os.path.exists(audio_file):
                overlay.set_state("error", _t("state_canceled"))
                time.sleep(1.0)
                overlay.after(0, overlay.destroy)
                return
                
            # 2. Transcription Phase
            # We import and call the transcribe functions from main
            from main import transcribe_gemini, transcribe_groq, transcribe_local_whisper
            
            engine = config.get("selected_engine", "gemini_cloud")
            if engine == "gemini_cloud":
                raw_text = transcribe_gemini(audio_file, config)
            elif engine == "groq_cloud":
                raw_text = transcribe_groq(audio_file, config)
            elif engine == "local_whisper":
                raw_text = transcribe_local_whisper(audio_file, config)
            else:
                raise ValueError(f"Ukendt motor: {engine}")
                
            if not raw_text.strip():
                overlay.set_state("error", _t("state_nothing_heard"))
                time.sleep(1.2)
                overlay.after(0, overlay.destroy)
                return
                
            # 3. Clean-up & Custom Dictionary
            dictionary = CustomDictionary(filepath=VOCAB_PATH)
            clean_text = dictionary.clean_text(raw_text)
            
            # 4. Rewrite (AI mode)
            if mode == "ai":
                overlay.set_state("processing", _t("state_rewriting"))
                rewriter = RewriteEngine(config)
                clean_text = rewriter.process(clean_text, style="clean_transcription")
            elif mode == "ai_prompt":
                overlay.set_state("processing", _t("state_rewriting"))
                rewriter = RewriteEngine(config)
                clean_text = rewriter.process(clean_text, style="cursor_prompt")
                
            # 5. Paste & Success State
            overlay.set_state("success", _t("state_inserting"))
            paster = ClipboardPaster()
            paster.paste(clean_text)
            
            time.sleep(0.5)
            
        except Exception as e:
            error_str = str(e)
            print(f"Error in overlay pipeline: {error_str}", file=sys.stderr)
            overlay.set_state("error", _t("state_error"))
            time.sleep(2.0)
        finally:
            # Active lock file cleanup
            try:
                if os.path.exists(LOCK_FILE):
                    os.remove(LOCK_FILE)
            except Exception:
                pass
                
            # Key-repeat suppression wait
            if initial_keys:
                display = None
                try:
                    if os.environ.get("XDG_SESSION_TYPE", "").lower() != "wayland":
                        import ctypes
                        try:
                            x11 = ctypes.CDLL('libX11.so.6')
                            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                            x11.XOpenDisplay.restype = ctypes.c_void_p
                            display = x11.XOpenDisplay(None)
                        except Exception:
                            pass
                            
                    while True:
                        curr = get_pressed_keys(display=display)
                        if curr is None:
                            break
                        still_down = initial_keys & curr
                        if not still_down:
                            break
                        time.sleep(0.05)
                finally:
                    if display:
                        try:
                            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                            x11.XCloseDisplay.restype = ctypes.c_int
                            x11.XCloseDisplay(display)
                        except Exception:
                            pass
                    
            # Fade-out window exit
            overlay.after(0, overlay.destroy)

    # Start pipeline thread
    pipeline_thread = threading.Thread(target=thread_target, daemon=True)
    pipeline_thread.start()
    
    # Block and run UI loop on main thread
    overlay.mainloop()

if __name__ == "__main__":
    os.chdir(SCRIPT_DIR)
    
    # Load config and run demo mode directly from terminal
    from main import load_config
    cfg = load_config()
    
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    start_overlay_pipeline(mode=run_mode, config=cfg)
