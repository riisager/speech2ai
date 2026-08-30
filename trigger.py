#!/usr/bin/env python3
import os
import sys
import socket
import subprocess

SOCKET_PATH = "/tmp/speech2ai.sock"

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCKET_PATH)
        s.sendall(mode.encode())
        s.close()
    except Exception as e:
        # Daemon is not active: trigger main.py as a seamless fallback
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(script_dir, "main.py")
        subprocess.Popen([sys.executable, main_path, mode])

if __name__ == "__main__":
    main()
