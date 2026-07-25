import tkinter as tk
import threading
import os
import logging


# ─── Sofortiger Splash-Screen ─────────────────────────────────────────────────
# Öffnet sich BEVOR schwere Imports (cv2, torch, numpy, gui) geladen werden.
# Dadurch erscheint der Splash quasi ohne Verzögerung beim Programmstart.

def _get_resource_path(relative_path: str) -> str:
    import sys
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def create_instant_splash():
    """Erstellt einen schlanken, hochmodernen Splash-Screen mit tkinter."""
    splash = tk.Tk()
    splash.title("IGNITE")
    splash.overrideredirect(True)
    splash.configure(bg="#07090E") # Cyber Obsidian Background
    splash.resizable(False, False)

    W, H = 520, 320
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")

    # Subtile leuchtende Umrandung (Cyber Glow Border Frame)
    border_frame = tk.Frame(splash, bg="#1E2638", bd=1)
    border_frame.place(x=0, y=0, width=W, height=H)

    inner_bg = tk.Frame(border_frame, bg="#07090E")
    inner_bg.place(x=1, y=1, width=W-2, height=H-2)

    # Logo
    logo_path = _get_resource_path(os.path.join("icon", "LogoRund.png"))
    logo_img_ref = None
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path).resize((72, 72), Image.LANCZOS)
        logo_img_ref = ImageTk.PhotoImage(img)
        tk.Label(inner_bg, image=logo_img_ref, bg="#07090E").pack(pady=(32, 8))
    except Exception as e:
        logging.debug(f"Fehler beim Laden des Splash-Logos: {e}")
        tk.Label(inner_bg, text="", bg="#07090E", height=3).pack()

    # Brand Title Stack
    tk.Label(inner_bg, text="IGNITE",
             font=("Segoe UI", 32, "bold"), fg="#F8FAFC", bg="#07090E").pack(pady=(0, 2))
    tk.Label(inner_bg, text="Medical Imaging Suite  ·  Jugend forscht 2026",
             font=("Segoe UI", 10, "bold"), fg="#818CF8", bg="#07090E").pack()

    # Trennlinie
    tk.Frame(inner_bg, bg="#1E2638", height=1).pack(fill=tk.X, padx=50, pady=16)

    status_var = tk.StringVar(value="Initialisiere High-Performance Engine...")
    tk.Label(inner_bg, textvariable=status_var,
             font=("Segoe UI", 10), fg="#94A3B8", bg="#07090E").pack(pady=(0, 10))

    # Fortschrittsbalken (Canvas Glow Indicator)
    pbar_canvas = tk.Canvas(inner_bg, width=380, height=4, bg="#0F1420",
                             highlightthickness=0, bd=0)
    pbar_canvas.pack()
    bar = pbar_canvas.create_rectangle(0, 0, 0, 4, fill="#6366F1", outline="")

    tk.Label(inner_bg, text="© 2026 Jona Noack  ·  Fachgebiet Arbeitswelt",
             font=("Segoe UI", 8), fg="#475569", bg="#07090E").pack(pady=(12, 4))

    # Referenzen sichern damit GC sie nicht löscht
    splash._logo_ref = logo_img_ref
    splash._pbar_canvas = pbar_canvas
    splash._pbar_bar = bar
    splash._status_var = status_var

    return splash


def update_splash(splash, progress: float, message: str):
    """Aktualisiert Fortschrittsbalken und Status-Label im Splash."""
    try:
        width = int(380 * progress)
        splash._pbar_canvas.coords(splash._pbar_bar, 0, 0, width, 4)
        splash._status_var.set(message)
        splash.update()
    except Exception as e:
        logging.debug(f"Splash-Fehler ignoriert: {e}")


# ─── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, filename='ignite_app.log', format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Splash sofort zeigen – noch BEVOR schwere Imports
    splash = create_instant_splash()
    splash.update()

    loaded = {}
    error_holder = {}

    def load_heavy():
        """Lädt alle schweren Abhängigkeiten im Background-Thread."""
        try:
            splash.after(0, lambda: update_splash(splash, 0.25, "Lade Bildverarbeitung..."))

            import customtkinter as ctk
            loaded["ctk"] = ctk

            splash.after(0, lambda: update_splash(splash, 0.55, "Initialisiere GPU-Backend..."))

            from gui.main_window import IgniteApp
            loaded["IgniteApp"] = IgniteApp

            splash.after(0, lambda: update_splash(splash, 0.85, "Lade Benutzeroberfläche..."))

            import time
            time.sleep(0.15)

            splash.after(0, lambda: update_splash(splash, 1.0, "Bereit."))
            time.sleep(0.2)

        except Exception as e:
            error_holder["error"] = str(e)
        finally:
            splash.after(0, _on_load_done)

    def _on_load_done():
        """Wird im Haupt-Thread aufgerufen wenn Loading fertig ist."""
        if "error" in error_holder:
            splash.destroy()
            import tkinter.messagebox as mb
            mb.showerror("Startfehler", f"Fehler beim Laden:\n{error_holder['error']}")
            return

        splash.destroy()

        ctk = loaded["ctk"]
        IgniteApp = loaded["IgniteApp"]

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        root = ctk.CTk()
        app = IgniteApp(root)
        root.mainloop()

    # Background-Thread starten
    t = threading.Thread(target=load_heavy, daemon=True)
    t.start()

    # Tkinter-Eventloop läuft bis _on_load_done() splash.destroy() aufruft
    splash.mainloop()


if __name__ == "__main__":
    main()
