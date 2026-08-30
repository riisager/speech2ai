import time
import queue
import os
import sys
import threading
import numpy as np
from system_compat import PlatformCompat

def get_pressed_keys(display=None):
    """Wrapper function preserving backward compatibility, delegating to PlatformCompat."""
    return PlatformCompat.get_pressed_keys(display=display)

def trim_silence(audio_data, sample_rate=16000, threshold_factor=1.8, min_padding_sec=0.12):
    """Trims leading and trailing silence from recorded audio using RMS energy.
    Greatly reduces audio payload size and transcription latency.
    """
    if len(audio_data) == 0:
        return audio_data

    # Convert to float for energy calculation
    float_audio = audio_data.astype(np.float32)
    frame_len = int(sample_rate * 0.03) # 30ms frames
    if frame_len <= 0 or len(audio_data) < frame_len * 2:
        return audio_data

    # Calculate frame RMS values
    num_frames = len(audio_data) // frame_len
    rms_values = []
    for i in range(num_frames):
        frame = float_audio[i * frame_len : (i + 1) * frame_len]
        rms = np.sqrt(np.mean(frame**2))
        rms_values.append(rms)

    if not rms_values:
        return audio_data

    # Compute adaptive noise floor threshold
    min_rms = np.percentile(rms_values, 15) # estimated background noise
    median_rms = np.median(rms_values)
    energy_threshold = max(350.0, min_rms * threshold_factor)

    # Find start and end active frames
    start_frame = 0
    end_frame = num_frames - 1

    for i in range(num_frames):
        if rms_values[i] > energy_threshold:
            start_frame = i
            break

    for i in range(num_frames - 1, -1, -1):
        if rms_values[i] > energy_threshold:
            end_frame = i
            break

    # Add safety padding around voice
    padding_frames = int(min_padding_sec * sample_rate / frame_len)
    start_idx = max(0, (start_frame - padding_frames) * frame_len)
    end_idx = min(len(audio_data), (end_frame + 1 + padding_frames) * frame_len)

    if end_idx <= start_idx:
        return audio_data

    return audio_data[start_idx:end_idx]


class AudioRecorder:
    """Thread-safe audio recording manager with silence trimming,
    interactive volume feedback, and dual Toggle/Hold recording modes.
    """
    current_volume = 0.0
    _stop_event = threading.Event()
    _cancel_event = threading.Event()

    @classmethod
    def request_stop(cls):
        """Signals the active recording session to stop and process captured audio."""
        cls._stop_event.set()

    @classmethod
    def request_cancel(cls):
        """Signals the active recording session to cancel immediately without processing."""
        cls._cancel_event.set()

    @classmethod
    def reset_events(cls):
        """Resets synchronization events before starting a new recording."""
        cls._stop_event.clear()
        cls._cancel_event.clear()

    @staticmethod
    def get_device_index_by_name(name):
        """Resolves an audio device name to its active sounddevice hardware index."""
        if not name:
            return None
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            # 1. Exact match
            for i, dev in enumerate(devices):
                if dev["name"] == name and dev["max_input_channels"] > 0:
                    return i
            # 2. Substring match
            for i, dev in enumerate(devices):
                if name in dev["name"] and dev["max_input_channels"] > 0:
                    return i
        except Exception:
            pass
        return None

    def __init__(self, sample_rate=16000, channels=1, device_name=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = self.get_device_index_by_name(device_name)

    def play_beep(self, frequency=550, duration=0.08, volume=0.15):
        """Plays a sine wave feedback tone asynchronously in a background thread."""
        import sounddevice as sd
        def _play():
            try:
                t = np.linspace(0, duration, int(self.sample_rate * duration), False)
                wave = np.sin(frequency * 2 * np.pi * t) * volume
                sd.play(wave.astype(np.float32), self.sample_rate)
                sd.wait()
            except Exception:
                pass

        threading.Thread(target=_play, daemon=True).start()

    def record(self, max_duration=30, output_path="/tmp/dictation.wav", enable_beeps=True, beep_volume=0.2, initial_keys=None, mode_preference="auto"):
        """Records audio from the microphone.
        Supports both Hold-to-Talk and Toggle (click/hotkey to stop) modes.
        """
        import sounddevice as sd

        AudioRecorder.reset_events()
        is_wayland = PlatformCompat.is_wayland()

        # Decide recording strategy: 'hold' or 'toggle'
        if mode_preference == "hold" and not is_wayland and initial_keys:
            use_key_release = True
        elif mode_preference == "toggle" or is_wayland:
            use_key_release = False
        else: # "auto"
            use_key_release = bool(initial_keys and not is_wayland)

        if use_key_release:
            print(f"Recording in Hold-to-Talk mode (Monitoring keys: {initial_keys})...")
        else:
            print("Recording in Toggle mode (Stop via hotkey, space, click, or timeout)...")

        # 1. Play start beep
        if enable_beeps:
            self.play_beep(frequency=650, duration=0.08, volume=beep_volume)

        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"Audio status warning: {status}", file=sys.stderr)
            audio_queue.put(indata.copy())
            try:
                rms = np.sqrt(np.mean(indata.astype(np.float32)**2))
                AudioRecorder.current_volume = min(1.0, rms / 3200.0)
            except Exception:
                AudioRecorder.current_volume = 0.0

        print("Audio stream recording active...")
        start_time = time.time()
        recorded_chunks = []
        sd.default.latency = "low"

        cancelled = False

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=self.channels, 
                                 device=self.device_index, dtype="int16", callback=callback):
                
                min_duration = 0.25
                released_consecutive_count = 0

                while True:
                    elapsed = time.time() - start_time

                    while not audio_queue.empty():
                        recorded_chunks.append(audio_queue.get())

                    # Check Cancellation
                    if AudioRecorder._cancel_event.is_set():
                        print("Recording cancelled by user.")
                        cancelled = True
                        break

                    # Check Explicit Stop
                    if AudioRecorder._stop_event.is_set():
                        print("Stop requested via event.")
                        break

                    # Check Timeout
                    if elapsed >= max_duration:
                        print(f"Reached maximum recording time ({max_duration}s).")
                        break

                    # Check external stop trigger file
                    if os.path.exists("/tmp/speech2ai2text_stop.trigger"):
                        try:
                            os.remove("/tmp/speech2ai2text_stop.trigger")
                        except Exception:
                            pass
                        print("Stop trigger file intercepted.")
                        break

                    # Hold-to-talk key release check (X11)
                    if use_key_release and elapsed >= min_duration:
                        current_keys = PlatformCompat.get_pressed_keys()
                        if current_keys is not None:
                            released = initial_keys - current_keys
                            if released:
                                released_consecutive_count += 1
                                if released_consecutive_count >= 2: # 100ms debounce
                                    print(f"Key release detected ({released}). Stopping.")
                                    break
                            else:
                                released_consecutive_count = 0

                    time.sleep(0.04)

        except Exception as e:
            print(f"Error in audio stream: {e}", file=sys.stderr)
            while not audio_queue.empty():
                recorded_chunks.append(audio_queue.get())

        # Play stop beep
        if enable_beeps and not cancelled:
            self.play_beep(frequency=450, duration=0.08, volume=beep_volume)

        if cancelled or not recorded_chunks:
            return None

        # 2. Process & Trim Silence
        try:
            import scipy.io.wavfile as wav
            raw_recording = np.concatenate(recorded_chunks, axis=0)

            # Apply intelligent silence trimming
            trimmed_recording = trim_silence(raw_recording, sample_rate=self.sample_rate)

            # Ensure non-empty
            if len(trimmed_recording) < int(self.sample_rate * 0.1):
                trimmed_recording = raw_recording

            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            wav.write(output_path, self.sample_rate, trimmed_recording)
            
            raw_dur = len(raw_recording) / self.sample_rate
            trim_dur = len(trimmed_recording) / self.sample_rate
            print(f"Saved audio: {output_path} ({trim_dur:.2f}s, trimmed from {raw_dur:.2f}s)")
            return output_path
        except Exception as e:
            print(f"Failed to write wav audio: {e}", file=sys.stderr)
            return None
