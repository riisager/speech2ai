import os
import sys
import datetime
import traceback

LOG_PATH = "/tmp/speech2ai.log"

def _format_log(level, msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return f"[{ts}] [{level}] {msg}\n"

def log_info(msg):
    try:
        line = _format_log("INFO", msg)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="", file=sys.stdout)
    except Exception:
        pass

def log_debug(msg):
    try:
        line = _format_log("DEBUG", msg)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="", file=sys.stdout)
    except Exception:
        pass

def log_error(msg, exc=None):
    try:
        if exc:
            msg = f"{msg}: {exc}\n{traceback.format_exc()}"
        line = _format_log("ERROR", msg)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="", file=sys.stderr)
    except Exception:
        pass
