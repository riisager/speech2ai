import sys
import os
import time

if __name__ == "__main__":
    try:
        log_file = open('/tmp/speech2ai2text.log', 'a', buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        pass
    print(f"\n--- Launching Speech2AI2Text at {time.ctime()} ---")

    # Prevent multiple concurrent instances (e.g. from keyboard auto-repeat)
    import fcntl
    import time
    try:
        lock_file = open('/tmp/speech2ai2text_singleton.lock', 'w')
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write current start time to the lock file
        lock_file.write(str(time.time()))
        lock_file.flush()
    except IOError:
        # Another instance is already running!
        # Only trigger a stop if the first instance has been running for at least 0.8 seconds.
        # This prevents keyboard auto-repeats from immediately killing the recording we just started.
        try:
            if os.path.exists('/tmp/speech2ai2text_singleton.lock'):
                with open('/tmp/speech2ai2text_singleton.lock', 'r') as f:
                    start_time_str = f.read().strip()
                    if start_time_str:
                        elapsed = time.time() - float(start_time_str)
                        if elapsed > 0.8:
                            with open('/tmp/speech2ai2text_stop.trigger', 'w') as tf:
                                tf.write('stop')
        except Exception:
            pass
        sys.exit(0)

import json
import subprocess
import requests

from audio_capture import AudioRecorder
from dictionary import CustomDictionary
from rewrite import RewriteEngine
from output import ClipboardPaster

# Resolve files relative to this script's directory for portability
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
VOCAB_PATH = os.path.join(SCRIPT_DIR, "vocabulary.json")
TEMP_WAV_PATH = "/tmp/speech2ai2text_dictation.wav"

def load_config():
    """Loads configuration with sane defaults."""
    default_config = {
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
        "enable_gui_overlay": True
    }
    
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_config.update(loaded)
        except Exception as e:
            print(f"Warning: Failed to load config.json: {e}", file=sys.stderr)
            
    return default_config

def send_notification(config, title, message, timeout=2000):
    """Sends a desktop notification using notify-send if enabled in config."""
    if not config.get("enable_notifications", True):
        return
    try:
        subprocess.run([
            "notify-send", 
            "-t", str(timeout), 
            "-i", "audio-input-microphone", 
            title, 
            message
        ], stderr=subprocess.DEVNULL)
    except Exception:
        pass

def transcribe_gemini(audio_path, config):
    """Transcribes audio using Gemini 1.5/2.0 API via direct HTTPS request."""
    api_key = config.get("gemini_api_key")
    model = config.get("gemini_model", "gemini-1.5-flash")
    
    if not api_key or "YOUR_" in api_key:
        raise ValueError("Mangler Gemini API nøgle. Indstil den venligst i config.json eller via settings_gui.py.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
        
    import base64
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"inlineData": {
                    "mimeType": "audio/wav",
                    "data": audio_b64
                }},
                {"text": "Transcribe the spoken audio exactly in its original language (Danish or English). Output ONLY the clean transcription text. No formatting, no extra explanation, no quotes, no chatty remarks."}
            ]
        }]
    }
    
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    
    if r.status_code == 200:
        res = r.json()
        try:
            text = res["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean up potential leading/trailing markdown wrapper or quotes
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1].strip()
            return text
        except (KeyError, IndexError):
            raise Exception("Modtog ugyldigt JSON-format fra Gemini API.")
    else:
        raise Exception(f"Gemini API svarede med fejl ({r.status_code}): {r.text}")

def transcribe_groq(audio_path, config):
    """Transcribes audio using Groq API via requests."""
    api_key = config.get("groq_api_key")
    
    if not api_key or "YOUR_" in api_key:
        raise ValueError("Mangler Groq API nøgle. Indstil den venligst i config.json eller via settings_gui.py.")
        
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
        data = {"model": "whisper-large-v3"}
        r = requests.post(url, headers=headers, files=files, data=data, timeout=20)
        
    if r.status_code == 200:
        return r.json().get("text", "").strip()
    else:
        raise Exception(f"Groq API svarede med fejl ({r.status_code}): {r.text}")

def transcribe_local_whisper(audio_path, config):
    """Transcribes audio using local whisper.cpp executable."""
    whisper_path = config.get("local_whisper_path", "")
    model_path = config.get("local_model_path", "")
    
    if not os.path.exists(whisper_path):
        raise FileNotFoundError(f"Lokal whisper.cpp executable ikke fundet på stien: {whisper_path}")
        
    cmd = [whisper_path]
    if model_path:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Whisper modelfil (.bin) ikke fundet på stien: {model_path}")
        cmd.extend(["-m", model_path])
        
    cmd.extend(["-f", audio_path, "-nt"])
    
    # whisper.cpp outputter transkribering til stdout og statistikker til stderr
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return res.stdout.strip()

def run_pipeline(mode="direct"):
    # Load configuration
    config = load_config()
    
    # Capture initially pressed keys for hold-to-record and repeat suppression
    from audio_capture import get_pressed_keys
    import time
    initial_keys = get_pressed_keys()
    if not initial_keys:
        time.sleep(0.05)
        initial_keys = get_pressed_keys()

    # Initialize notification feedback
    send_notification(config, "Speech2AI2Text", "🎤 Lytter... (Hold genvejstast nede)", timeout=1500)
    
    # Create active lock file for tray icon status change
    LOCK_FILE = "/tmp/speech2ai2text_active.lock"
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(mode)
    except Exception:
        pass

    try:
        # 1. Optag lyd fra mikrofon
        recorder = AudioRecorder()
        audio_file = recorder.record(
            max_duration=config.get("max_recording_time", 30), 
            output_path=TEMP_WAV_PATH, 
            enable_beeps=config.get("enable_beeps", True),
            beep_volume=config.get("beep_volume", 0.2),
            initial_keys=initial_keys
        )
    finally:
        # Remove active lock file
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass
            
    if not audio_file or not os.path.exists(audio_file):
        send_notification(config, "Speech2AI2Text", "❌ Optagelse fejlede eller blev afbrudt.", timeout=1500)
        return
        
    # Transition feedback
    send_notification(config, "Speech2AI2Text", "⚡ Bearbejder lyd...", timeout=2500)
    
    # 2. Transkriber
    engine = config.get("selected_engine", "gemini_cloud")
    print(f"Transcribing using: {engine}")
    
    try:
        if engine == "gemini_cloud":
            raw_text = transcribe_gemini(audio_file, config)
        elif engine == "groq_cloud":
            raw_text = transcribe_groq(audio_file, config)
        elif engine == "local_whisper":
            raw_text = transcribe_local_whisper(audio_file, config)
        else:
            raise ValueError(f"Ukendt transkriberingsmotor valgt: {engine}")
            
        print(f"Raw transcription: '{raw_text}'")
        
        if not raw_text.strip():
            send_notification(config, "Speech2AI2Text", "⚠️ Intet tale detekteret.", timeout=1500)
            return
            
        # 3. Kør igennem den lokale ordbog
        dictionary = CustomDictionary(filepath=VOCAB_PATH)
        clean_text = dictionary.clean_text(raw_text)
        print(f"Cleaned transcription: '{clean_text}'")
        
        # 4. Hvis vi er i AI-mode, kør omskriveren
        if mode == "ai":
            send_notification(config, "Speech2AI2Text", "🤖 Retter tekst med AI...", timeout=2500)
            rewriter = RewriteEngine(config)
            clean_text = rewriter.process(clean_text, style="clean_transcription")
            print(f"AI proofread text: '{clean_text}'")
        elif mode == "ai_prompt":
            send_notification(config, "Speech2AI2Text", "🤖 Genererer AI Prompt...", timeout=2500)
            rewriter = RewriteEngine(config)
            clean_text = rewriter.process(clean_text, style="cursor_prompt")
            print(f"Rewritten coding prompt: '{clean_text}'")
            
        # 5. Paste resultatet lynhurtigt
        paster = ClipboardPaster()
        paster.paste(clean_text)
        
        # Success feedback
        send_notification(config, "Speech2AI2Text", "✅ Færdig! Tekst indsat.", timeout=1000)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Pipeline error: {error_msg}", file=sys.stderr)
        send_notification(config, "Speech2AI2Text Fejl", error_msg, timeout=4000)

    # Wait until the physical shortcut keys are fully released before exiting.
    # This prevents the OS from triggering a new process immediately due to key auto-repeat.
    if initial_keys:
        from audio_capture import get_pressed_keys
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
                current_keys = get_pressed_keys(display=display)
                if current_keys is None:
                    break
                # If none of the initial keys are still pressed, we can exit
                still_pressed = initial_keys & current_keys
                if not still_pressed:
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

if __name__ == "__main__":
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    
    config = load_config()
    if config.get("enable_gui_overlay", True):
        from gui_overlay import start_overlay_pipeline
        start_overlay_pipeline(mode=run_mode, config=config)
    else:
        run_pipeline(mode=run_mode)
