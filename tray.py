import os
import sys
import subprocess
import time
import threading
from PIL import Image, ImageDraw

# Fallback check for pystray and pillow
try:
    import pystray
except ImportError:
    print("Error: pystray is not installed. Run ./install.sh first.", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = "/tmp/speech2ai2text_active.lock"

def create_mic_icon(color):
    """Generates a 64x64 pixel transparent PNG microphone icon programmatically."""
    # Create transparent image
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw mic head (rounded capsule)
    # [x0, y0, x1, y1]
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
    """Triggers the dictation script manually."""
    subprocess.Popen([
        sys.executable,
        os.path.join(SCRIPT_DIR, "main.py"),
        mode
    ])

def on_menu_clicked(icon, item):
    """Callback for menu item clicks."""
    name = str(item)
    if name == "Indstillinger (Settings)...":
        launch_settings()
    elif name == "Start Diktat":
        trigger_dictation("direct")
    elif name == "Start AI Diktat (Grammatik)":
        trigger_dictation("ai")
    elif name == "Start AI Coding Prompt":
        trigger_dictation("ai_prompt")
    elif name == "Afslut (Exit)":
        icon.stop()

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
    
    # Pre-set default icon
    icon.icon = idle_icon
    
    is_recording = False
    
    while icon.visible:
        # Check if the lock file exists (indicating main.py is recording audio)
        lock_exists = os.path.exists(LOCK_FILE)
        
        if lock_exists != is_recording:
            is_recording = lock_exists
            if is_recording:
                icon.icon = active_icon
                icon.title = "Speech2AI2Text - Optager..."
            else:
                icon.icon = idle_icon
                icon.title = "Speech2AI2Text"
                
        time.sleep(0.1)

def run_tray():
    # Load default idle icon
    idle_icon_path = os.path.join(SCRIPT_DIR, "speech2ai2text_icon.png")
    try:
        initial_icon = Image.open(idle_icon_path)
        initial_icon.load()
    except Exception:
        initial_icon = create_mic_icon((230, 230, 230, 255))
    
    # Construct menu
    menu = pystray.Menu(
        pystray.MenuItem("Speech2AI2Text Linux", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start Diktat", on_menu_clicked),
        pystray.MenuItem("Start AI Diktat (Grammatik)", on_menu_clicked),
        pystray.MenuItem("Start AI Coding Prompt", on_menu_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Indstillinger (Settings)...", on_menu_clicked, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Afslut (Exit)", on_menu_clicked)
    )
    
    icon = pystray.Icon(
        "speech2ai2text", 
        icon=initial_icon, 
        title="Speech2AI2Text", 
        menu=menu
    )
    
    # Start background polling thread
    monitor_thread = threading.Thread(target=monitor_recording_state, args=(icon,), daemon=True)
    monitor_thread.start()
    
    # Run the tray icon main loop (blocks until icon.stop() is called)
    icon.run()

if __name__ == "__main__":
    # Ensure working directory is set to script's location
    os.chdir(SCRIPT_DIR)
    
    # Prevent duplicate system tray instances
    import fcntl
    try:
        tray_lock = open('/tmp/speech2ai2text_tray_singleton.lock', 'w')
        fcntl.lockf(tray_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Keep lock file reference alive
        tray_lock.write(str(time.time()))
        tray_lock.flush()
    except IOError:
        print("Speech2AI2Text Tray is already running. Exiting.")
        sys.exit(0)
        
    run_tray()
