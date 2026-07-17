import time
import queue
import ctypes
import os
import sys

# Initialize X11 multi-threading support to prevent segmentation faults
# when X11 functions are called from background threads alongside Tkinter.
try:
    x11 = ctypes.CDLL('libX11.so.6')
    x11.XInitThreads()
except Exception:
    pass

def get_pressed_keys(display=None):
    """Queries the X11 server for all currently pressed physical keycodes.
    Uses direct X11 connection (thread-safe by opening its own display connection)
    with automatic fallback to xinput.
    """
    try:
        x11 = ctypes.CDLL('libX11.so.6')
        
        # Explicitly define ctypes signatures to prevent 64-bit pointer truncation crashes
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        
        x11.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        x11.XQueryKeymap.restype = ctypes.c_int
        
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.restype = ctypes.c_int
        
        # Open a thread-local display connection to ensure X11 thread safety
        local_display = x11.XOpenDisplay(None)
        if local_display:
            keys = (ctypes.c_char * 32)()
            x11.XQueryKeymap(local_display, keys)
            x11.XCloseDisplay(local_display)
            
            pressed = set()
            for i in range(32):
                val = keys[i]
                if isinstance(val, bytes):
                    byte_val = val[0]
                elif isinstance(val, str):
                    byte_val = ord(val)
                else:
                    byte_val = int(val)
                for bit in range(8):
                    if byte_val & (1 << bit):
                        pressed.add(i * 8 + bit)
            return pressed
    except Exception:
        pass

    # Fallback to querying xinput slave devices (useful for Wayland or if ctypes fails)
    import subprocess
    pressed = set()
    try:
        out = subprocess.check_output(["xinput", "list"], text=True, env={"DISPLAY": ":0"})
        kbd_ids = []
        for line in out.splitlines():
            if "slave  keyboard" in line.lower() and "id=" in line.lower():
                name = line.lower()
                if any(x in name for x in ["control", "button", "bus", "jack", "power", "sleep", "xtest", "mouse"]):
                    continue
                parts = line.split("id=")
                if len(parts) > 1:
                    idx = parts[1].split()[0]
                    idx = "".join(c for c in idx if c.isdigit())
                    if idx:
                        kbd_ids.append(int(idx))
                        
        for kid in kbd_ids:
            try:
                state_out = subprocess.check_output(["xinput", "query-state", str(kid)], text=True, stderr=subprocess.DEVNULL, env={"DISPLAY": ":0"})
                for line in state_out.splitlines():
                    if "=down" in line:
                        key_part = line.split("key[")
                        if len(key_part) > 1:
                            key_num = key_part[1].split("]")[0]
                            pressed.add(int(key_num))
            except Exception:
                continue
        return pressed
    except Exception:
        return None

class AudioRecorder:
    current_volume = 0.0
    stop_requested = False

    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels

    def play_beep(self, frequency=550, duration=0.08, volume=0.15):
        """Plays a programmatic sine wave beep tone asynchronously in a background thread."""
        import numpy as np
        import sounddevice as sd
        def _play():
            try:
                t = np.linspace(0, duration, int(self.sample_rate * duration), False)
                wave = np.sin(frequency * 2 * np.pi * t) * volume
                sd.play(wave.astype(np.float32), self.sample_rate)
                sd.wait()
            except Exception:
                pass
        
        import threading
        threading.Thread(target=_play, daemon=True).start()

    def record(self, max_duration=30, output_path="/tmp/dictation.wav", enable_beeps=True, beep_volume=0.2, initial_keys=None):
        """Records audio from the microphone. Stops when shortcut keys are released or max_duration is met."""
        import numpy as np
        import sounddevice as sd
        display = None
        try:
            if os.environ.get("XDG_SESSION_TYPE", "").lower() != "wayland":
                try:
                    x11 = ctypes.CDLL('libX11.so.6')
                    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                    x11.XOpenDisplay.restype = ctypes.c_void_p
                    display = x11.XOpenDisplay(None)
                except Exception:
                    pass

            # 1. Detect shortcut keys initially pressed on launch if not passed
            if initial_keys is None:
                initial_keys = get_pressed_keys(display=display)
                
                # Let's wait a tiny bit to make sure we catch keys if there's latency
                if not initial_keys:
                    time.sleep(0.05)
                    initial_keys = get_pressed_keys(display=display)
                
            use_key_release = False
            if initial_keys:
                # We only monitor keys that are actually pressed.
                # Usually includes modifier keys (Super/Ctrl) and the trigger key.
                print(f"Detected shortcut keycodes: {initial_keys}")
                use_key_release = True
            else:
                print("No shortcut keys detected. Will record until max duration or Ctrl+C.")
    
            # 2. Play start beep
            if enable_beeps:
                self.play_beep(frequency=650, duration=0.08, volume=beep_volume)
    
            # Queue to pass audio data from stream callback to recorder thread
            audio_queue = queue.Queue()
    
            def callback(indata, frames, time_info, status):
                if status:
                    print(f"Audio stream status warning: {status}", file=sys.stderr)
                audio_queue.put(indata.copy())
                try:
                    rms = np.sqrt(np.mean(indata.astype(np.float32)**2))
                    AudioRecorder.current_volume = min(1.0, rms / 3500.0)
                except Exception:
                    AudioRecorder.current_volume = 0.0
    
            # 3. Start audio input stream
            print("Recording started...")
            start_time = time.time()
            recorded_chunks = []
            
            # Set low latency suggestion
            sd.default.latency = 'low'
            
            try:
                with sd.InputStream(samplerate=self.sample_rate, channels=self.channels, 
                                     dtype='int16', callback=callback):
                    
                    # Minimum duration to avoid instant triggers from key bounce
                    min_duration = 0.3
                    
                    released_consecutive_count = 0
                    while True:
                        elapsed = time.time() - start_time
                        
                        # Read all available audio data
                        while not audio_queue.empty():
                            recorded_chunks.append(audio_queue.get())
                            
                        # Stop conditions
                        if elapsed >= max_duration:
                            print("Reached maximum duration.")
                            break
                            
                        if AudioRecorder.stop_requested:
                            AudioRecorder.stop_requested = False
                            print("External stop requested via GUI click.")
                            break
                            
                        if os.path.exists('/tmp/speech2ai2text_stop.trigger'):
                            try:
                                os.remove('/tmp/speech2ai2text_stop.trigger')
                            except Exception:
                                pass
                            print("Stop trigger file detected (shortcut double-press).")
                            break
                            
                        if use_key_release and elapsed >= min_duration:
                            current_keys = get_pressed_keys(display=display)
                            if current_keys is not None:
                                # If any of the initially pressed keys were released
                                released = initial_keys - current_keys
                                if released:
                                    released_consecutive_count += 1
                                    if released_consecutive_count >= 3: # Must be released for 3 consecutive checks (150ms)
                                        print(f"Key release detected (keycodes {released}). Stopping.")
                                        break
                                else:
                                    released_consecutive_count = 0
                                    
                        time.sleep(0.05)
                        
            except Exception as e:
                print(f"Error during audio recording: {e}", file=sys.stderr)
                # Try to grab remaining queue items
                while not audio_queue.empty():
                    recorded_chunks.append(audio_queue.get())
    
            # Play stop beep
            if enable_beeps:
                self.play_beep(frequency=450, duration=0.08, volume=beep_volume)
    
            if not recorded_chunks:
                print("No audio captured.")
                return None
    
            # 4. Save to WAV file
            try:
                import scipy.io.wavfile as wav
                recording = np.concatenate(recorded_chunks, axis=0)
                # Ensure the directory exists
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                wav.write(output_path, self.sample_rate, recording)
                print(f"Saved recording to {output_path} ({len(recording)/self.sample_rate:.2f}s)")
                return output_path
            except Exception as e:
                print(f"Failed to write wav file: {e}", file=sys.stderr)
                return None
        finally:
            if display:
                try:
                    x11 = ctypes.CDLL('libX11.so.6')
                    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                    x11.XCloseDisplay.restype = ctypes.c_int
                    x11.XCloseDisplay(display)
                except Exception:
                    pass
