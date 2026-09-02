import os
import sys
import subprocess
import time
import threading
import socket
import requests
import json
from PIL import Image, ImageDraw
from i18n import _t

# Fallback check for pystray and pillow
try:
    import pystray
except ImportError:
    print("Error: pystray is not installed. Run ./install.sh first.", file=sys.stderr)
    sys.exit(1)

# Fallback check for customtkinter
try:
    import customtkinter as ctk
except ImportError:
    print("Error: customtkinter is not installed.", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
LOCK_FILE = "/tmp/speech2ai2text_active.lock"
SOCKET_PATH = "/tmp/speech2ai.sock"

# Re-use config and overlay classes
from main import load_config
from gui_overlay import RecordingOverlay, start_overlay_pipeline

# Global variables for the daemon references
global_overlay = None
global_config = None
global_session = None

def create_mic_icon(color):
    """Generates a 64x64 pixel transparent PNG microphone icon programmatically."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw mic head (rounded capsule)
    draw.rounded_rectangle([22, 10, 42, 38], radius=8, fill=color)
    
    # Draw U-shape stand around the capsule
    draw.arc([16, 20, 48, 44], start=0, end=180, fill=color, width=4)
    
    # Draw vertical neck support
    draw.line([32, 44, 32, 54], fill=color, width=4)
    
    # Draw horizontal bottom base plate
    draw.line([20, 54, 44, 54], fill=color, width=4)
    
    return image

def launch_settings():
    """Launches the settings panel in a separate process."""
    subprocess.Popen([
        sys.executable,
        os.path.join(SCRIPT_DIR, "settings_gui.py")
    ])

def trigger_dictation(mode):
    """Triggers dictation warm start internally on the main Tkinter thread."""
    global global_overlay, global_config, global_session
    if global_overlay:
        global_overlay.after(0, lambda m=mode: start_recording_from_socket(global_overlay, global_config, m, global_session))

def send_desktop_notification(title, message):
    try:
        subprocess.run(["notify-send", "-a", "Speech2AI", title, message], check=False)
    except Exception:
        pass

def copy_last_transcription():
    """Copies the latest transcribed text back to the system clipboard and notifies user."""
    last_text_path = "/tmp/speech2ai_last_text.txt"
    if os.path.exists(last_text_path):
        try:
            with open(last_text_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                try:
                    subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=False)
                except Exception:
                    pass
                from audio_capture import play_audio_cue
                play_audio_cue("success", volume=0.2)
                preview = text[:55] + "..." if len(text) > 55 else text
                send_desktop_notification("Speech2AI", f"{_t('tray_copied_toast')}\n\"{preview}\"")
                return
        except Exception:
            pass
    send_desktop_notification("Speech2AI", _t("tray_no_last_text"))

def update_config_value(key, value):
    """Dynamically updates a configuration setting and notifies user."""
    try:
        cfg = load_config()
        cfg[key] = value
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        from logger import log_info
        log_info(f"Tray updated config {key} -> {value}")
        send_desktop_notification("Speech2AI", _t("tray_model_switched").format(model=value))
    except Exception as e:
        from logger import log_error
        log_error(f"Failed to update config {key}: {e}")

def on_menu_clicked(icon, item):
    """Callback for menu item clicks."""
    name = str(item)
    if name == _t("tray_settings"):
        launch_settings()
    elif name == _t("tray_direct"):
        trigger_dictation("direct")
    elif name == _t("tray_ai"):
        trigger_dictation("ai")
    elif name == _t("tray_prompt"):
        trigger_dictation("ai_prompt")
    elif name == _t("tray_exit"):
        icon.stop()
        try:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
        except Exception:
            pass
        os._exit(0)

def build_tray_menu(icon_ref=None):
    """Builds a rich dynamic tray menu with quick-actions and model selection."""
    cfg = load_config()
    curr_stt = cfg.get("gemini_model", "gemini-3.5-transcribe")
    curr_rewrite = cfg.get("gemini_rewrite_model", "gemini-flash-lite-latest")
    
    def set_stt(m):
        def _cb(icon, item):
            update_config_value("gemini_model", m)
            if icon_ref:
                icon_ref.menu = build_tray_menu(icon_ref)
        return _cb
        
    def set_rewrite(m):
        def _cb(icon, item):
            update_config_value("gemini_rewrite_model", m)
            if icon_ref:
                icon_ref.menu = build_tray_menu(icon_ref)
        return _cb

    stt_menu = pystray.Menu(
        pystray.MenuItem("gemini-3.5-transcribe (Anbefalet)", set_stt("gemini-3.5-transcribe"), checked=lambda item: curr_stt == "gemini-3.5-transcribe", radio=True),
        pystray.MenuItem("gemini-flash-latest", set_stt("gemini-flash-latest"), checked=lambda item: curr_stt == "gemini-flash-latest", radio=True),
        pystray.MenuItem("gemini-flash-lite-latest", set_stt("gemini-flash-lite-latest"), checked=lambda item: curr_stt == "gemini-flash-lite-latest", radio=True),
        pystray.MenuItem("gemini-3.5-flash", set_stt("gemini-3.5-flash"), checked=lambda item: curr_stt == "gemini-3.5-flash", radio=True),
        pystray.MenuItem("gemini-3.5-flash-lite", set_stt("gemini-3.5-flash-lite"), checked=lambda item: curr_stt == "gemini-3.5-flash-lite", radio=True),
    )
    
    rewrite_menu = pystray.Menu(
        pystray.MenuItem("gemini-flash-lite-latest (Anbefalet)", set_rewrite("gemini-flash-lite-latest"), checked=lambda item: curr_rewrite == "gemini-flash-lite-latest", radio=True),
        pystray.MenuItem("gemini-flash-latest", set_rewrite("gemini-flash-latest"), checked=lambda item: curr_rewrite == "gemini-flash-latest", radio=True),
        pystray.MenuItem("gemini-3.5-flash", set_rewrite("gemini-3.5-flash"), checked=lambda item: curr_rewrite == "gemini-3.5-flash", radio=True),
        pystray.MenuItem("gemini-3.5-pro", set_rewrite("gemini-3.5-pro"), checked=lambda item: curr_rewrite == "gemini-3.5-pro", radio=True),
    )

    return pystray.Menu(
        pystray.MenuItem("🎙️ Speech2AI v2.5", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_copy_last"), lambda icon, item: copy_last_transcription()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_stt_model"), stt_menu),
        pystray.MenuItem(_t("tray_rewrite_model"), rewrite_menu),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_direct"), on_menu_clicked),
        pystray.MenuItem(_t("tray_ai"), on_menu_clicked),
        pystray.MenuItem(_t("tray_prompt"), on_menu_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_settings"), on_menu_clicked, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_exit"), on_menu_clicked)
    )

def monitor_recording_state(icon):
    """Background loop that updates the tray icon color based on active recording locks."""
    idle_icon_path = os.path.join(SCRIPT_DIR, "speech2ai2text_icon.png")
    active_icon_path = os.path.join(SCRIPT_DIR, "speech2ai2text_icon_recording.png")
    
    try:
        idle_icon = Image.open(idle_icon_path)
        idle_icon.load()
    except Exception:
        idle_icon = create_mic_icon((230, 230, 230, 255))
        
    try:
        active_icon = Image.open(active_icon_path)
        active_icon.load()
    except Exception:
        active_icon = create_mic_icon((255, 60, 60, 255))
    
    icon.icon = idle_icon
    is_recording = False
    
    while icon.visible:
        lock_exists = os.path.exists(LOCK_FILE)
        if lock_exists != is_recording:
            is_recording = lock_exists
            if is_recording:
                icon.icon = active_icon
                icon.title = f"Speech2AI - {_t('state_recording')}"
            else:
                icon.icon = idle_icon
                icon.title = "Speech2AI"
        time.sleep(0.1)

def run_tray():
    idle_icon_path = os.path.join(SCRIPT_DIR, "speech2ai2text_icon.png")
    try:
        initial_icon = Image.open(idle_icon_path)
        initial_icon.load()
    except Exception:
        initial_icon = create_mic_icon((230, 230, 230, 255))
    
    icon = pystray.Icon(
        "speech2ai", 
        icon=initial_icon, 
        title="Speech2AI"
    )
    icon.menu = build_tray_menu(icon)
    
    monitor_thread = threading.Thread(target=monitor_recording_state, args=(icon,), daemon=True)
    monitor_thread.start()
    icon.run()

def start_recording_from_socket(overlay, config, mode, session):
    """Callback triggered on the main thread to run the visual pipeline."""
    from logger import log_info, log_error
    if os.path.exists(LOCK_FILE):
        log_info("Recording is already active. Ignoring socket trigger.")
        return
        
    # Query which keys are currently held down for hold-to-record
    from audio_capture import get_pressed_keys
    initial_keys = get_pressed_keys()
    log_info(f"Trigger received via UNIX socket for mode: '{mode}' | initial_keys: {initial_keys}")
    
    # Reload config dynamically before triggering the run
    fresh_config = load_config()
    start_overlay_pipeline(
        mode=mode, 
        config=fresh_config, 
        overlay=overlay, 
        initial_keys=initial_keys, 
        session=session
    )

def run_socket_server(overlay, config, session):
    """UNIX socket server that listens for instant client triggers."""
    from logger import log_info, log_error
    if os.path.exists(SOCKET_PATH):
        try:
            os.unlink(SOCKET_PATH)
        except Exception:
            pass
            
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)
    log_info(f"UNIX socket server listening on {SOCKET_PATH}")
    
    while True:
        try:
            conn, addr = server.accept()
            data = conn.recv(1024)
            if data:
                mode = data.decode().strip()
                log_info(f"Socket incoming connection accepted (mode: '{mode}')")
                # Schedule overlay activation on Tkinter main thread
                overlay.after(0, lambda m=mode: start_recording_from_socket(overlay, config, m, session))
            conn.close()
        except Exception as e:
            log_error(f"Socket server error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    os.chdir(SCRIPT_DIR)
    
    # Prevent duplicate system tray daemon instances
    import fcntl
    try:
        tray_lock = open('/tmp/speech2ai2text_tray_singleton.lock', 'w')
        fcntl.lockf(tray_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tray_lock.write(str(time.time()))
        tray_lock.flush()
    except IOError:
        print("Speech2AI2Text Tray is already running. Exiting.")
        sys.exit(0)
        
    # Setup connection pooling session
    global_session = requests.Session()
    global_config = load_config()
    
    # Instantiate the persistent Tkinter overlay on the main thread
    global_overlay = RecordingOverlay(mode="direct", config=global_config, persistent=True)
    global_overlay.withdraw()  # Hide overlay window initially
    
    # Start UNIX Socket Server in a background thread
    socket_thread = threading.Thread(
        target=run_socket_server, 
        args=(global_overlay, global_config, global_session), 
        daemon=True
    )
    socket_thread.start()
    
    # Start System Tray Icon loop in a background thread
    tray_thread = threading.Thread(target=run_tray, daemon=True)
    tray_thread.start()
    
    # Start Tkinter event mainloop on the main thread (blocks persistently)
    global_overlay.mainloop()
