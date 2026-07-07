import tkinter as tk
import threading
import os


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
    """Erstellt einen schlanken Splash-Screen mit tkinter (kein customtkinter nötig)."""
    splash = tk.Tk()
    splash.title("IGNITE")
    splash.overrideredirect(True)
    splash.configure(bg="#030712") # Neue Hintergrundfarbe Gray-950
    splash.resizable(False, False)

    W, H = 480, 300
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")

    # Logo
    logo_path = _get_resource_path(os.path.join("icon", "LogoRund.png"))
    logo_img_ref = None
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path).resize((64, 64), Image.LANCZOS)
        logo_img_ref = ImageTk.PhotoImage(img)
        tk.Label(splash, image=logo_img_ref, bg="#030712").pack(pady=(36, 6))
    except Exception:
        tk.Label(splash, text="", bg="#030712", height=3).pack()

    # Font stack: Segoe UI
    tk.Label(splash, text="IGNITE",
             font=("Segoe UI", 30, "bold"), fg="#F8FAFC", bg="#030712").pack(pady=(0, 3))
    tk.Label(splash, text="Medical Imaging Suite  ·  Jugend forscht 2026",
             font=("Segoe UI", 11), fg="#94A3B8", bg="#030712").pack()

    tk.Frame(splash, bg="#1E293B", height=1).pack(fill=tk.X, padx=40, pady=14)

    status_var = tk.StringVar(value="Lade Module...")
    tk.Label(splash, textvariable=status_var,
             font=("Segoe UI", 11), fg="#475569", bg="#030712").pack()

    tk.Label(splash, text="© 2026 Jona Noack  ·  Jugend forscht",
             font=("Segoe UI", 9), fg="#1E293B", bg="#030712").pack(pady=(10, 6))

    # Fortschrittsbalken (simuliert via Canvas)
    pbar_canvas = tk.Canvas(splash, width=360, height=3, bg="#0B0F19",
                             highlightthickness=0, bd=0)
    pbar_canvas.pack()
    bar = pbar_canvas.create_rectangle(0, 0, 0, 3, fill="#6366F1", outline="") # Neue Akzentfarbe Indigo

    # Referenzen sichern damit GC sie nicht löscht
    splash._logo_ref = logo_img_ref
    splash._pbar_canvas = pbar_canvas
    splash._pbar_bar = bar
    splash._status_var = status_var

    return splash


def update_splash(splash, progress: float, message: str):
    """Aktualisiert Fortschrittsbalken und Status-Label im Splash."""
    try:
        width = int(360 * progress)
        splash._pbar_canvas.coords(splash._pbar_bar, 0, 0, width, 3)
        splash._status_var.set(message)
        splash.update()
    except Exception:
        pass


# ─── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
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

            from gui import IgniteApp
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
