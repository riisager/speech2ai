import sys
import os
import time
import json
import subprocess
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from i18n import _t

from audio_capture import AudioRecorder
from dictionary import CustomDictionary
from rewrite import RewriteEngine
from output import ClipboardPaster
from system_compat import PlatformCompat

# Resolve files relative to this script's directory for portability
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
VOCAB_PATH = os.path.join(SCRIPT_DIR, "vocabulary.json")
TEMP_WAV_PATH = "/tmp/speech2ai2text_dictation.wav"

def create_resilient_session():
    """Builds a high-performance requests Session with Keep-Alive pooling
    and automatic retry backoff on transient errors.
    """
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.2,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def prewarm_connection(config, session):
    """Sends a lightweight pre-flight probe asynchronously to establish and warm up
    the TLS socket while the user is still speaking.
    """
    if not session:
        return

    def _ping():
        engine = config.get("selected_engine", "gemini_cloud")
        try:
            if engine == "gemini_cloud":
                session.head("https://generativelanguage.googleapis.com", timeout=1.5)
            elif engine == "groq_cloud":
                session.head("https://api.groq.com", timeout=1.5)
        except Exception:
            pass

    threading.Thread(target=_ping, daemon=True).start()

def load_config():
    """Loads configuration with sane defaults."""
    default_config = {
        "selected_engine": "gemini_cloud",
        "rewrite_locally": False,
        "local_llm_model": "gemma4:e4b",
        "local_whisper_path": "/usr/bin/whisper",
        "local_model_path": "",
        "groq_api_key": "",
        "gemini_api_key": "",
        "gemini_model": "gemini-3.5-flash",
        "enable_notifications": False,
        "enable_beeps": True,
        "beep_volume": 0.2,
        "enable_gui_overlay": True,
        "recording_mode": "auto", # 'auto', 'toggle', 'hold'
        "input_device": "",
        "language": "en"
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

def transcribe_gemini(audio_path, config, session=None):
    """Transcribes audio using Gemini API via direct HTTPS request with connection reuse."""
    api_key = config.get("gemini_api_key")
    model = config.get("gemini_model", "gemini-1.5-flash")
    
    if not api_key or "YOUR_" in api_key:
        raise ValueError(_t("missing_key_gemini"))
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
        
    import base64
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    
    payload = {
        "contents": [{
            "parts": [
                {"inlineData": {
                    "mimeType": "audio/wav",
                    "data": audio_b64
                }},
                {"text": "Transcribe the spoken audio accurately in its original language (Danish or English). Output ONLY the clean transcription text. No formatting, no conversational explanation, no quotes."}
            ]
        }]
    }
    
    headers = {"Content-Type": "application/json"}
    post_func = session.post if session else requests.post
    r = post_func(url, headers=headers, json=payload, timeout=20)
    
    if r.status_code == 200:
        res = r.json()
        try:
            text = res["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1].strip()
            return text
        except (KeyError, IndexError):
            raise Exception("Modtog ugyldigt JSON-format fra Gemini API.")
    else:
        raise Exception(f"Gemini API fejl ({r.status_code}): {r.text}")

def transcribe_groq(audio_path, config, session=None):
    """Transcribes audio using Groq Whisper API via requests."""
    api_key = config.get("groq_api_key")
    
    if not api_key or "YOUR_" in api_key:
        raise ValueError("Mangler Groq API nøgle. Indstil den venligst i config.json eller via settings_gui.py.")
        
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
        data = {"model": "whisper-large-v3"}
        post_func = session.post if session else requests.post
        r = post_func(url, headers=headers, files=files, data=data, timeout=20)
        
    if r.status_code == 200:
        return r.json().get("text", "").strip()
    else:
        raise Exception(f"Groq API fejl ({r.status_code}): {r.text}")

def transcribe_local_whisper(audio_path, config):
    """Transcribes audio using local whisper.cpp executable."""
    whisper_path = config.get("local_whisper_path", "")
    model_path = config.get("local_model_path", "")
    
    if not os.path.exists(whisper_path):
        raise FileNotFoundError(f"Lokal whisper.cpp executable ikke fundet på: {whisper_path}")
        
    cmd = [whisper_path]
    if model_path:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Whisper model ikke fundet på: {model_path}")
        cmd.extend(["-m", model_path])
        
    cmd.extend(["-f", audio_path, "-nt"])
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return res.stdout.strip()

def run_pipeline(mode="direct"):
    """Cold-start fallback execution pipeline."""
    config = load_config()
    session = create_resilient_session()
    
    selected_text = ""
    if mode != "direct":
        selected_text = PlatformCompat.get_selected_text()

    initial_keys = PlatformCompat.get_pressed_keys()
    send_notification(config, "Speech2AI", _t("notify_listening"), timeout=1500)
    
    LOCK_FILE = "/tmp/speech2ai2text_active.lock"
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(mode)
    except Exception:
        pass

    try:
        # Pre-warm TLS connection while user speaks
        prewarm_connection(config, session)

        recorder = AudioRecorder(device_name=config.get("input_device"))
        audio_file = recorder.record(
            max_duration=config.get("max_recording_time", 30), 
            output_path=TEMP_WAV_PATH, 
            enable_beeps=config.get("enable_beeps", True),
            beep_volume=config.get("beep_volume", 0.2),
            initial_keys=initial_keys,
            mode_preference=config.get("recording_mode", "auto")
        )
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass
            
    if not audio_file or not os.path.exists(audio_file):
        send_notification(config, "Speech2AI", _t("notify_failed"), timeout=1500)
        return
        
    send_notification(config, "Speech2AI", _t("notify_processing"), timeout=2500)
    engine = config.get("selected_engine", "gemini_cloud")
    
    try:
        if engine == "gemini_cloud":
            raw_text = transcribe_gemini(audio_file, config, session=session)
        elif engine == "groq_cloud":
            raw_text = transcribe_groq(audio_file, config, session=session)
        elif engine == "local_whisper":
            raw_text = transcribe_local_whisper(audio_file, config)
        else:
            raise ValueError(f"{_t('unknown_engine')}{engine}")
            
        if not raw_text.strip():
            send_notification(config, "Speech2AI", _t("notify_no_speech"), timeout=1500)
            return
            
        dictionary = CustomDictionary(filepath=VOCAB_PATH)
        clean_text = dictionary.clean_text(raw_text)
        
        if mode == "ai":
            send_notification(config, "Speech2AI", _t("notify_rewriting_ai"), timeout=2500)
            rewriter = RewriteEngine(config, session=session)
            clean_text = rewriter.process(clean_text, style="clean_transcription", selected_text=selected_text)
        elif mode == "ai_prompt":
            send_notification(config, "Speech2AI", _t("notify_generating_prompt"), timeout=2500)
            rewriter = RewriteEngine(config, session=session)
            clean_text = rewriter.process(clean_text, style="cursor_prompt", selected_text=selected_text)
            
        ClipboardPaster.paste(clean_text)
        send_notification(config, "Speech2AI", _t("notify_success"), timeout=1000)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Pipeline error: {error_msg}", file=sys.stderr)
        send_notification(config, _t("notify_error_title"), error_msg, timeout=4000)

if __name__ == "__main__":
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    cfg = load_config()
    
    if cfg.get("enable_gui_overlay", True):
        from gui_overlay import start_overlay_pipeline
        start_overlay_pipeline(mode=run_mode, config=cfg)
    else:
        run_pipeline(mode=run_mode)
