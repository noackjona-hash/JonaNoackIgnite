"""
generate_gui_screenshot.py
Startet die IGNITE Anwendung im Hintergrund und speichert einen echten UI-Screenshot des Dashboards.
"""

import os
import sys
import time
import customtkinter as ctk
from PIL import ImageGrab

# Projekt-Root ermitteln, damit relative Pfade (images/, ...) sowie der Import
# von gui.main_window trotz Verschiebung nach scripts/ weiterhin funktionieren.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

os.makedirs("images", exist_ok=True)

try:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("IGNITE Medical Imaging Suite")
    root.geometry("1280x800")
    
    from gui.main_window import IgniteApp
    app = IgniteApp(root)
    
    root.update_idletasks()
    root.update()
    time.sleep(1.0)
    root.update()
    
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    
    if w > 100 and h > 100:
        bbox = (x, y, x + w, y + h)
        img_grab = ImageGrab.grab(bbox)
        img_grab.save("images/ignite_gui_dashboard.png")
        print("[+] GUI Dashboard Screenshot gespeichert in images/ignite_gui_dashboard.png.")
    
    root.destroy()
except Exception as e:
    print(f"[!] Info zur GUI-Erzeugung: {e}")
