"""
Launcher: startuje serwer Flask w tle, pokazuje ikone w zasobniku systemowym
(kolor = ogolny status wszystkich sesji) i na pierwszy rzut otwiera dashboard
jako osobne okienko (Edge w trybie --app; w razie braku Edge - zwykla przegladarka).
"""
import os
import sys
import time
import subprocess
import threading
import webbrowser

import requests
from PIL import Image, ImageDraw
import pystray

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 5151
URL = f"http://{HOST}:{PORT}/"

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# priorytet kategorii przy wielu sesjach naraz (najwazniejsza wygrywa)
CATEGORY_PRIORITY = ["error", "stale", "waiting", "working", "done", "info", "ended"]
CATEGORY_COLOR = {
    "error": (239, 68, 68),
    "stale": (249, 115, 22),
    "waiting": (245, 158, 11),
    "working": (59, 130, 246),
    "done": (34, 197, 94),
    "info": (167, 139, 250),
    "ended": (107, 114, 128),
}
CATEGORY_LABEL = {
    "error": "Błąd narzędzia",
    "stale": "Może się zawiesił",
    "waiting": "Czeka na Ciebie",
    "working": "Pracuje",
    "done": "Gotowe",
    "info": "Aktywność",
    "ended": "Zakończona",
}


def start_server():
    sys.path.insert(0, BASE_DIR)
    from app import app
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def open_window():
    edge = next((p for p in EDGE_PATHS if os.path.exists(p)), None)
    if edge:
        subprocess.Popen([edge, f"--app={URL}", "--window-size=460,720"])
    else:
        webbrowser.open(URL)


def make_icon_image(color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((6, 6, 58, 58), fill=color)
    return img


def overall_status():
    try:
        resp = requests.get(f"{URL}api/status", timeout=1.5)
        sessions = resp.json().get("sessions", [])
    except Exception:
        return "ended", "Serwer niedostępny"

    if not sessions:
        return "ended", "Brak aktywnych sesji"

    categories = {s.get("status_category", "info") for s in sessions}
    for cat in CATEGORY_PRIORITY:
        if cat in categories:
            n = len(sessions)
            label = f"{CATEGORY_LABEL.get(cat, cat)} ({n} sesj{'a' if n == 1 else 'e' if n < 5 else 'i'})"
            return cat, label
    return "info", "Aktywność"


def status_watcher(icon):
    time.sleep(2)
    while True:
        cat, label = overall_status()
        icon.icon = make_icon_image(CATEGORY_COLOR.get(cat, (107, 114, 128)))
        icon.title = f"Claude Code Monitor — {label}"
        time.sleep(3)


def on_open(icon, item):
    open_window()


def on_quit(icon, item):
    icon.stop()
    os._exit(0)


if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=lambda: (time.sleep(1.2), open_window()), daemon=True).start()

    tray_icon = pystray.Icon(
        "claude_code_monitor",
        make_icon_image(CATEGORY_COLOR["ended"]),
        "Claude Code Monitor",
        menu=pystray.Menu(
            pystray.MenuItem("Otwórz Monitor", on_open, default=True),
            pystray.MenuItem("Zamknij", on_quit),
        ),
    )
    threading.Thread(target=status_watcher, args=(tray_icon,), daemon=True).start()
    tray_icon.run()
