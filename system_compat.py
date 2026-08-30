import os
import sys
import subprocess
import ctypes

class PlatformCompat:
    """Unified system compatibility layer for Linux desktop environments.
    Seamlessly handles display server differences (Wayland vs. X11),
    window managers (Cinnamon, GNOME, KDE, Sway, Hyprland), and input tools.
    """

    @staticmethod
    def is_wayland():
        """Returns True if the current session is running under Wayland."""
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
        return (session_type == "wayland") or bool(wayland_display)

    @staticmethod
    def get_session_info():
        """Returns diagnostic info about the active desktop environment and display server."""
        return {
            "session_type": "wayland" if PlatformCompat.is_wayland() else "x11",
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
            "display": os.environ.get("DISPLAY", ":0"),
            "wayland_display": os.environ.get("WAYLAND_DISPLAY", "")
        }

    @staticmethod
    def clear_primary_selection():
        """Clears the transient primary selection buffer to prevent stale highlights from persisting."""
        is_wayland = PlatformCompat.is_wayland()
        if is_wayland:
            try:
                subprocess.run(["wl-copy", "--primary", "--clear"], stderr=subprocess.DEVNULL, timeout=0.1)
            except Exception:
                pass
        else:
            try:
                p = subprocess.Popen(["xclip", "-selection", "primary", "-in"], stdin=subprocess.PIPE)
                p.communicate(input=b"", timeout=0.1)
            except Exception:
                pass

    @staticmethod
    def get_selected_text():
        """Captures the active highlighted/selected text passively.
        Directly queries the X11 / Wayland PRIMARY selection buffer.
        """
        is_wayland = PlatformCompat.is_wayland()
        selected_text = ""

        if is_wayland:
            try:
                out = subprocess.check_output(
                    ["wl-paste", "--primary", "--no-newline"], 
                    stderr=subprocess.DEVNULL,
                    timeout=0.08
                )
                selected_text = out.decode("utf-8", errors="ignore").strip()
            except Exception:
                pass
        else:
            try:
                out = subprocess.check_output(
                    ["xclip", "-selection", "primary", "-o"], 
                    stderr=subprocess.DEVNULL,
                    timeout=0.08
                )
                selected_text = out.decode("utf-8", errors="ignore").strip()
            except Exception:
                pass

        # Sanitize and truncate excessively large selections
        if len(selected_text) > 3000:
            selected_text = selected_text[:3000]

        return selected_text

    @staticmethod
    def paste_text(text):
        """Pastes the text into the active field and leaves it in the clipboard permanently."""
        if not text:
            return

        is_wayland = PlatformCompat.is_wayland()

        if is_wayland:
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(input=text.encode("utf-8"), timeout=0.5)
            except Exception as e:
                print(f"Wayland wl-copy error: {e}", file=sys.stderr)

            pasted = False
            try:
                subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True, stderr=subprocess.DEVNULL, timeout=0.3)
                pasted = True
            except Exception:
                pass

            if not pasted:
                try:
                    subprocess.run(["wtype", "-M", "ctrl", "v"], check=True, stderr=subprocess.DEVNULL, timeout=0.3)
                    pasted = True
                except Exception:
                    pass

            PlatformCompat.clear_primary_selection()

        else:
            # X11 implementation
            try:
                p = subprocess.Popen(["xclip", "-selection", "clipboard", "-in"], stdin=subprocess.PIPE)
                p.communicate(input=text.encode("utf-8"), timeout=0.5)

                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], timeout=0.5)
            except Exception as e:
                print(f"X11 paste failed: {e}", file=sys.stderr)
                try:
                    subprocess.run(["xdotool", "type", "--delay", "5", text], timeout=1.5)
                except Exception:
                    pass

            PlatformCompat.clear_primary_selection()

    @staticmethod
    def get_pressed_keys(display=None):
        """Thread-safe physical keycode query for X11. Returns set of keycodes or empty set on Wayland."""
        if PlatformCompat.is_wayland():
            return set()

        try:
            x11 = ctypes.CDLL("libX11.so.6")
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            x11.XQueryKeymap.restype = ctypes.c_int
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.restype = ctypes.c_int

            local_display = x11.XOpenDisplay(None)
            if local_display:
                keys = (ctypes.c_char * 32)()
                x11.XQueryKeymap(local_display, keys)
                x11.XCloseDisplay(local_display)

                pressed = set()
                for i in range(32):
                    val = keys[i]
                    byte_val = val[0] if isinstance(val, bytes) else ord(val) if isinstance(val, str) else int(val)
                    for bit in range(8):
                        if byte_val & (1 << bit):
                            pressed.add(i * 8 + bit)
                return pressed
        except Exception:
            pass

        return set()
