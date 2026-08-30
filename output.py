import subprocess
import time
import os
import sys

class ClipboardPaster:
    @staticmethod
    def paste(text):
        """Pastes the text by writing it to the clipboard and triggering Ctrl+V.
        Leaves the pasted text in the clipboard so the user can paste it again.
        """
        if not text:
            return
            
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = (session == "wayland")
        
        if not is_wayland:
            # --- X11 implementation using xclip and xdotool ---
            try:
                # 1. Put new text in clipboard
                p = subprocess.Popen(["xclip", "-selection", "clipboard", "-in"], stdin=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'))

                # 2. Trigger Ctrl+V
                # We use --clearmodifiers to prevent physical keys (like Super or Shift)
                # from interfering with the Ctrl+V key combination.
                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
            except Exception as e:
                print(f"X11 paste failed: {e}", file=sys.stderr)
                # Fallback to direct typing if clipboard paste failed
                try:
                    subprocess.run(["xdotool", "type", "--delay", "10", text])
                except Exception:
                    pass
        else:
            # --- Wayland implementation fallback ---
            print("Wayland session detected. Attempting wl-copy and paste...", file=sys.stderr)
            try:
                # Copy new text to clipboard
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'))

                # Trigger paste - ydotool requires setup, wtype is another fallback.
                # We attempt ydotool first, then wtype, then print a notice.
                ydotool_success = False
                try:
                    # ydotool key ctrl+v (29 = ctrl, 47 = v)
                    # We send key down and up events
                    subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True, stderr=subprocess.DEVNULL)
                    ydotool_success = True
                except Exception:
                    pass

                if not ydotool_success:
                    try:
                        # Try wtype (which simulates typing in Wayland)
                        # wtype -M ctrl v
                        subprocess.run(["wtype", "-M", "ctrl", "v"], check=True, stderr=subprocess.DEVNULL)
                    except Exception:
                        print("Warning: Neither ydotool nor wtype could trigger Ctrl+V on Wayland.", file=sys.stderr)
            except Exception as e:
                print(f"Wayland copy/paste failed: {e}", file=sys.stderr)

    @staticmethod
    def get_selected_text():
        """Attempts to retrieve currently selected/highlighted text using Ctrl+C simulation."""
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = (session == "wayland")
        
        selected_text = ""
        if not is_wayland:
            # --- X11 implementation ---
            old_clip = None
            try:
                # 1. Backup existing clipboard content
                old_clip = subprocess.check_output(
                    ["xclip", "-selection", "clipboard", "-o"], 
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

            try:
                # 2. Clear clipboard
                p = subprocess.Popen(["xclip", "-selection", "clipboard", "-in"], stdin=subprocess.PIPE)
                p.communicate(input=b"")

                # 3. Trigger Ctrl+C (copy selection)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+c"])
                
                # Wait briefly for selection to copy
                time.sleep(0.15)
                
                # 4. Read clipboard
                text_bytes = subprocess.check_output(
                    ["xclip", "-selection", "clipboard", "-o"], 
                    stderr=subprocess.DEVNULL
                )
                selected_text = text_bytes.decode('utf-8', errors='ignore').strip()
                
                # 5. Restore original clipboard
                if old_clip is not None:
                    p = subprocess.Popen(["xclip", "-selection", "clipboard", "-in"], stdin=subprocess.PIPE)
                    p.communicate(input=old_clip)
            except Exception as e:
                print(f"X11 get selected text failed: {e}", file=sys.stderr)
        else:
            # --- Wayland implementation ---
            old_clip = None
            try:
                # Backup
                old_clip = subprocess.check_output(["wl-paste", "-n"], stderr=subprocess.DEVNULL)
            except Exception:
                pass

            try:
                # Clear clipboard
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(input=b"")

                # Trigger Ctrl+C
                ydotool_success = False
                try:
                    # ydotool key ctrl+c (29 = ctrl, 46 = c)
                    subprocess.run(["ydotool", "key", "29:1", "46:1", "46:0", "29:0"], check=True, stderr=subprocess.DEVNULL)
                    ydotool_success = True
                except Exception:
                    pass

                if not ydotool_success:
                    try:
                        subprocess.run(["wtype", "-M", "ctrl", "c"], check=True, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

                time.sleep(0.15)
                
                # Read selection
                text_bytes = subprocess.check_output(["wl-paste", "-n"], stderr=subprocess.DEVNULL)
                selected_text = text_bytes.decode('utf-8', errors='ignore').strip()
                
                # Restore
                if old_clip is not None:
                    p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                    p.communicate(input=old_clip)
            except Exception as e:
                print(f"Wayland get selected text failed: {e}", file=sys.stderr)

        return selected_text
