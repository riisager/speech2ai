import os
import subprocess

def render_svg_to_png(svg_path, png_path, bg_color_override=None):
    with open(svg_path, "r") as f:
        svg_content = f.read()

    if bg_color_override:
        # Replace the light blue fill (#77b3d4) with the override color (e.g. red for recording)
        svg_content = svg_content.replace('fill:#77b3d4', f'fill:{bg_color_override}')

    # Adjust the width and height attributes in the SVG to fit the 256x256 frame
    svg_content = svg_content.replace('height="800"', 'height="256"')
    svg_content = svg_content.replace('width="800"', 'width="256"')

    html_path = f"/tmp/render_icon_{os.path.basename(png_path)}.html"
    html_content = f"""<!DOCTYPE html>
    <html>
    <head>
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        width: 256px;
        height: 256px;
        background: transparent;
        overflow: hidden;
      }}
      svg {{
        width: 256px;
        height: 256px;
        display: block;
      }}
    </style>
    </head>
    <body>
    {svg_content}
    </body>
    </html>
    """

    with open(html_path, "w") as f:
        f.write(html_content)

    # Run headless chrome to capture a transparent screenshot of the SVG
    cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        f"--screenshot={png_path}",
        "--window-size=256,256",
        "--default-background-color=00000000",
        html_path
    ]
    subprocess.run(cmd, check=True)
    
    # Cleanup temp html
    try:
        os.remove(html_path)
    except Exception:
        pass

def generate():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(BASE_DIR, "icon.svg")

    if not os.path.exists(svg_path):
        print(f"Error: {svg_path} not found.")
        return

    # 1. Render standard idle icon (light blue background)
    png_idle = os.path.join(BASE_DIR, "speech2ai2text_icon.png")
    render_svg_to_png(svg_path, png_idle)
    print(f"Generated idle icon at: {png_idle}")

    # 2. Render active recording icon (red background)
    png_rec = os.path.join(BASE_DIR, "speech2ai2text_icon_recording.png")
    render_svg_to_png(svg_path, png_rec, bg_color_override="#d32f2f")
    print(f"Generated recording icon at: {png_rec}")

if __name__ == "__main__":
    generate()
