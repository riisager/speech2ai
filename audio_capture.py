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

    @staticmethod
    def get_device_index_by_name(name):
        if not name:
            return None
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['name'] == name and dev['max_input_channels'] > 0:
                    return i
            for i, dev in enumerate(devices):
                if name in dev['name'] and dev['max_input_channels'] > 0:
                    return i
        except Exception:
            pass
        return None

    def __init__(self, sample_rate=16000, channels=1, device_name=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.capture_rate = 48000
        self.capture_channels = 2
        self.device_index = self.get_device_index_by_name(device_name)

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

            from logger import log_info, log_error, log_debug
            log_info(f"Audio recording initialized. Device: {self.device_index}, CaptureRate: {self.capture_rate}Hz, TargetRate: {self.sample_rate}Hz")
            
            # 1. Detect shortcut keys initially pressed on launch if not passed
            if initial_keys is None:
                initial_keys = get_pressed_keys(display=display)
                if not initial_keys:
                    time.sleep(0.05)
                    initial_keys = get_pressed_keys(display=display)
                
            use_key_release = False
            if initial_keys:
                log_info(f"Detected held shortcut keycodes: {initial_keys} (hold-to-talk mode active)")
                use_key_release = True
            else:
                log_info("No shortcut keys held on trigger. Recording until timeout or manual stop.")
    
            # 2. Play start beep
            if enable_beeps:
                self.play_beep(frequency=650, duration=0.08, volume=beep_volume)
    
            # 3. Start audio input stream
            log_info("Audio stream open and actively recording...")
            start_time = time.time()
            recorded_chunks = []
            
            try:
                with sd.InputStream(samplerate=self.capture_rate, channels=self.capture_channels, 
                                     device=self.device_index, dtype='float32') as stream:
                    
                    min_duration = 0.3
                    released_consecutive_count = 0
                    while True:
                        elapsed = time.time() - start_time
                        
                        # Read 1024 frames (~21ms of audio at 48kHz) directly from hardware stream
                        chunk, overflowed = stream.read(1024)
                        recorded_chunks.append(chunk)
                        
                        # Live volume for HUD overlay animation
                        try:
                            mono_chunk = np.mean(chunk, axis=1) if chunk.ndim > 1 else chunk
                            rms = np.sqrt(np.mean(mono_chunk.astype(np.float32)**2))
                            AudioRecorder.current_volume = min(1.0, float(rms * 10.0))
                        except Exception:
                            AudioRecorder.current_volume = 0.0
                            
                        if elapsed >= max_duration:
                            log_info(f"Recording stopped: Reached maximum duration ({max_duration}s).")
                            break
                            
                        if AudioRecorder.stop_requested:
                            AudioRecorder.stop_requested = False
                            log_info("Recording stopped: External stop requested via GUI click.")
                            break
                            
                        if os.path.exists('/tmp/speech2ai2text_stop.trigger'):
                            try:
                                os.remove('/tmp/speech2ai2text_stop.trigger')
                            except Exception:
                                pass
                            log_info("Recording stopped: Stop trigger file intercepted.")
                            break
                            
                        if use_key_release and elapsed >= min_duration:
                            current_keys = get_pressed_keys(display=display)
                            if current_keys is not None:
                                released = initial_keys - current_keys
                                if released:
                                    released_consecutive_count += 1
                                    if released_consecutive_count >= 3:
                                        log_info(f"Recording stopped: Key release detected (released keycodes: {released}) after {elapsed:.2f}s.")
                                        break
                                else:
                                    released_consecutive_count = 0
                        
            except Exception as e:
                log_error(f"Error during audio recording stream: {e}")
    
            # Play stop beep
            if enable_beeps:
                self.play_beep(frequency=450, duration=0.08, volume=beep_volume)
    
            if not recorded_chunks:
                log_error("No audio chunks were captured from the stream.")
                return None
    
            # 4. Process and Save to WAV file
            try:
                import scipy.io.wavfile as wav
                import scipy.signal
                raw_audio = np.concatenate(recorded_chunks, axis=0)
                
                # Convert stereo to mono
                if raw_audio.ndim > 1:
                    mono_audio = np.mean(raw_audio, axis=1)
                else:
                    mono_audio = raw_audio
                    
                # Resample 48000Hz -> 16000Hz (downsample 3:1)
                if self.capture_rate != self.sample_rate:
                    mono_16k = scipy.signal.resample_poly(mono_audio, self.sample_rate // 1000, self.capture_rate // 1000)
                else:
                    mono_16k = mono_audio
                    
                # Convert float32 [-1.0, 1.0] to int16 PCM
                int16_audio = np.clip(mono_16k * 32767.0, -32768, 32767).astype(np.int16)
                dur = len(int16_audio) / self.sample_rate
                rms = np.sqrt(np.mean(int16_audio.astype(np.float32)**2)) if len(int16_audio) > 0 else 0
                max_amp = np.max(np.abs(int16_audio)) if len(int16_audio) > 0 else 0
                
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                wav.write(output_path, self.sample_rate, int16_audio)
                log_info(f"Saved audio to {output_path} | Duration: {dur:.2f}s | RMS: {rms:.2f} | MaxPeak: {max_amp}")
                return output_path
            except Exception as e:
                log_error(f"Failed to write wav file: {e}")
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
