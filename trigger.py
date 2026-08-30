#!/usr/bin/env python3
import os
import sys
import time
import socket
import subprocess

SOCKET_PATH = "/tmp/speech2ai.sock"
DEBOUNCE_FILE = "/tmp/speech2ai_trigger.debounce"

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    now = time.time()

    # 1. Rate-limit triggers to prevent keyboard auto-repeat spam (min 350ms between trigger executions)
    try:
        if os.path.exists(DEBOUNCE_FILE):
            with open(DEBOUNCE_FILE, "r") as f:
                last_time = float(f.read().strip() or 0)
            if now - last_time < 0.35:
                # Fired too quickly (keyboard auto-repeat). Safely ignore.
                sys.exit(0)
    except Exception:
        pass

    try:
        with open(DEBOUNCE_FILE, "w") as f:
            f.write(str(now))
    except Exception:
        pass

    # 2. Dispatch to daemon or cold-start fallback
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect(SOCKET_PATH)
        s.sendall(mode.encode())
        s.close()
    except Exception:
        # Daemon is not active: trigger main.py as a fallback
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(script_dir, "main.py")
        subprocess.Popen([sys.executable, main_path, mode])

if __name__ == "__main__":
    main()
