import os
import sys
import subprocess
import time
import threading
import socket
import signal
import atexit
from PIL import Image, ImageDraw
from i18n import _t

try:
    import pystray
except ImportError:
    print("Error: pystray is not installed. Run ./install.sh first.", file=sys.stderr)
    sys.exit(1)

try:
    import customtkinter as ctk
except ImportError:
    print("Error: customtkinter is not installed.", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = "/tmp/speech2ai2text_active.lock"
TRAY_LOCK_FILE = "/tmp/speech2ai2text_tray_singleton.lock"
SOCKET_PATH = "/tmp/speech2ai.sock"

from main import load_config, create_resilient_session
from gui_overlay import RecordingOverlay, start_overlay_pipeline
from audio_capture import AudioRecorder
from system_compat import PlatformCompat

def cleanup():
    """Removes transient sockets and locks on daemon exit."""
    try:
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
    except Exception:
        pass
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass
    try:
        if os.path.exists(TRAY_LOCK_FILE):
            os.remove(TRAY_LOCK_FILE)
    except Exception:
        pass

atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

global_overlay = None
global_config = None
global_session = None

def create_mic_icon(color):
    """Generates a 64x64 transparent PNG microphone icon programmatically."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([22, 10, 42, 38], radius=8, fill=color)
    draw.arc([16, 20, 48, 44], start=0, end=180, fill=color, width=4)
    draw.line([32, 44, 32, 54], fill=color, width=4)
    draw.line([20, 54, 44, 54], fill=color, width=4)
    return image

def launch_settings():
    subprocess.Popen([
        sys.executable,
        os.path.join(SCRIPT_DIR, "settings_gui.py")
    ])

def trigger_dictation(mode):
    global global_overlay, global_config, global_session
    if global_overlay:
        global_overlay.after(0, lambda m=mode: start_recording_from_socket(global_overlay, global_config, m, global_session))

def on_menu_clicked(icon, item):
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
        cleanup()
        os._exit(0)

def monitor_recording_state(icon):
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
    
    menu = pystray.Menu(
        pystray.MenuItem("Speech2AI", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_direct"), on_menu_clicked),
        pystray.MenuItem(_t("tray_ai"), on_menu_clicked),
        pystray.MenuItem(_t("tray_prompt"), on_menu_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_settings"), on_menu_clicked, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("tray_exit"), on_menu_clicked)
    )
    
    icon = pystray.Icon(
        "speech2ai", 
        icon=initial_icon, 
        title="Speech2AI", 
        menu=menu
    )
    
    monitor_thread = threading.Thread(target=monitor_recording_state, args=(icon,), daemon=True)
    monitor_thread.start()
    icon.run()

pipeline_active = False
pipeline_start_time = 0.0

def start_recording_from_socket(overlay, config, mode, session):
    """Runs the visual pipeline or stops recording if a second trigger is received."""
    global pipeline_active, pipeline_start_time
    now = time.time()
    
    if pipeline_active:
        # Only stop if at least 0.5s has elapsed since recording started
        if now - pipeline_start_time >= 0.5:
            print("Toggle stop requested via secondary trigger.")
            AudioRecorder.request_stop()
        else:
            print("Ignored rapid duplicate trigger (<0.5s).")
        return

    # Mark active synchronously on main thread BEFORE spawning background pipeline
    pipeline_active = True
    pipeline_start_time = now

    def on_pipeline_finished():
        global pipeline_active
        pipeline_active = False

    initial_keys = PlatformCompat.get_pressed_keys()
    fresh_config = load_config()
    start_overlay_pipeline(
        mode=mode, 
        config=fresh_config, 
        overlay=overlay, 
        initial_keys=initial_keys, 
        session=session,
        on_finish_callback=on_pipeline_finished
    )

def run_socket_server(overlay, config, session):
    """UNIX socket server that listens for instant client triggers."""
    if os.path.exists(SOCKET_PATH):
        try:
            os.unlink(SOCKET_PATH)
        except Exception:
            pass
            
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)
    
    while True:
        try:
            conn, addr = server.accept()
            data = conn.recv(1024)
            if data:
                mode = data.decode().strip()
                overlay.after(0, lambda m=mode: start_recording_from_socket(overlay, config, m, session))
            conn.close()
        except Exception as e:
            print(f"Socket server error: {e}", file=sys.stderr)
            time.sleep(1)

if __name__ == "__main__":
    os.chdir(SCRIPT_DIR)
    
    import fcntl
    try:
        tray_lock = open(TRAY_LOCK_FILE, "w")
        fcntl.lockf(tray_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tray_lock.write(str(time.time()))
        tray_lock.flush()
    except IOError:
        print("Speech2AI2Text Tray is already running. Exiting.")
        sys.exit(0)
        
    global_session = create_resilient_session()
    global_config = load_config()
    
    global_overlay = RecordingOverlay(mode="direct", config=global_config, persistent=True)
    global_overlay.withdraw()
    
    socket_thread = threading.Thread(
        target=run_socket_server, 
        args=(global_overlay, global_config, global_session), 
        daemon=True
    )
    socket_thread.start()
    
    tray_thread = threading.Thread(target=run_tray, daemon=True)
    tray_thread.start()
    
    global_overlay.mainloop()
