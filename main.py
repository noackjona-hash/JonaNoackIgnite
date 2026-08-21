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


def _enable_dpi_awareness() -> None:
    """Aktiviert unter Windows die DPI-Awareness des Prozesses.

    Muss aufgerufen werden BEVOR das erste Fenster (Splash) erzeugt wird, damit
    tkinter und CustomTkinter die echte Bildschirm-DPI erhalten. Andernfalls
    meldet Windows faelschlich 96 DPI und die Oberflaeche wirkt auf
    HiDPI-Displays winzig.
    """
    import sys
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        # PROCESS_SYSTEM_DPI_AWARE (1): einheitlich & scharf fuer eine Ein-Fenster-App
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception as e:
            logging.debug(f"DPI-Awareness konnte nicht gesetzt werden: {e}")


def _dpi_scale_for(win) -> float:
    """Ermittelt den DPI-Skalierungsfaktor (1.0 = 96 DPI) fuer ein Fenster."""
    try:
        return max(1.0, round(win.winfo_fpixels("1i") / 96.0, 2))
    except Exception:
        return 1.0


def create_instant_splash():
    """Erstellt einen schlichten, DPI-skalierten Standard-Splash-Screen."""
    splash = tk.Tk()
    splash.title("IGNITE")
    splash.overrideredirect(True)
    splash.configure(bg="#FFFFFF")
    splash.resizable(False, False)

    # DPI-Skalierung ermitteln, damit der Splash auf HiDPI nicht winzig wirkt
    s = _dpi_scale_for(splash)
    px = lambda v: int(round(v * s))
    fs = lambda v: max(1, int(round(v * s)))

    W, H = px(520), px(320)
    bar_w = px(380)
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")

    # Schlichter grauer Rahmen
    border_frame = tk.Frame(splash, bg="#C0C0C0", bd=0)
    border_frame.place(x=0, y=0, width=W, height=H)

    inner_bg = tk.Frame(border_frame, bg="#FFFFFF")
    inner_bg.place(x=1, y=1, width=W-2, height=H-2)

    # Logo
    logo_path = _get_resource_path(os.path.join("icon", "LogoRund.png"))
    logo_img_ref = None
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path).resize((px(72), px(72)), Image.LANCZOS)
        logo_img_ref = ImageTk.PhotoImage(img)
        tk.Label(inner_bg, image=logo_img_ref, bg="#FFFFFF").pack(pady=(px(32), px(8)))
    except Exception as e:
        logging.debug(f"Fehler beim Laden des Splash-Logos: {e}")
        tk.Label(inner_bg, text="", bg="#FFFFFF", height=3).pack()

    # Titel
    tk.Label(inner_bg, text="IGNITE",
             font=("Segoe UI", -fs(42), "bold"), fg="#1A1A1A", bg="#FFFFFF").pack(pady=(0, px(2)))
    tk.Label(inner_bg, text="Medical Imaging Suite  -  Jugend forscht 2026",
             font=("Segoe UI", -fs(14)), fg="#444444", bg="#FFFFFF").pack()

    # Trennlinie
    tk.Frame(inner_bg, bg="#D0D0D0", height=1).pack(fill=tk.X, padx=px(50), pady=px(16))

    status_var = tk.StringVar(value="Wird geladen...")
    tk.Label(inner_bg, textvariable=status_var,
             font=("Segoe UI", -fs(13)), fg="#767676", bg="#FFFFFF").pack(pady=(0, px(10)))

    # Fortschrittsbalken
    pbar_canvas = tk.Canvas(inner_bg, width=bar_w, height=px(4), bg="#E8E8E8",
                             highlightthickness=0, bd=0)
    pbar_canvas.pack()
    bar = pbar_canvas.create_rectangle(0, 0, 0, px(4), fill="#1A73E8", outline="")

    tk.Label(inner_bg, text="© 2026 Jona Noack  ·  Fachgebiet Arbeitswelt",
             font=("Segoe UI", -fs(11)), fg="#80868B", bg="#FFFFFF").pack(pady=(px(12), px(4)))

    # Referenzen sichern damit GC sie nicht löscht
    splash._logo_ref = logo_img_ref
    splash._pbar_canvas = pbar_canvas
    splash._pbar_bar = bar
    splash._status_var = status_var
    splash._pbar_width = bar_w
    splash._pbar_height = px(4)

    return splash


def update_splash(splash, progress: float, message: str):
    """Aktualisiert Fortschrittsbalken und Status-Label im Splash."""
    try:
        width = int(splash._pbar_width * progress)
        splash._pbar_canvas.coords(splash._pbar_bar, 0, 0, width, splash._pbar_height)
        splash._status_var.set(message)
        splash.update()
    except Exception as e:
        logging.debug(f"Splash-Fehler ignoriert: {e}")


# ─── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=os.path.join(log_dir, 'ignite_app.log'), format='%(asctime)s - %(levelname)s - %(message)s')

    # DPI-Awareness AKTIVIEREN bevor das erste Fenster erzeugt wird
    _enable_dpi_awareness()

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

        import config
        sw = splash.winfo_screenwidth()
        sh = splash.winfo_screenheight()
        
        # Automatische responsive Skalierung für moderne High-DPI Displays (z.B. 1440p / 4K)
        if sw >= 3200 or sh >= 1800:
            auto_scale = 1.55
        elif sw >= 2200 or sh >= 1300:
            auto_scale = 1.30
        elif sw >= 1800:
            auto_scale = 1.15
        else:
            auto_scale = 1.0

        dpi_scale = max(_dpi_scale_for(splash), auto_scale)
        ui_scale = dpi_scale * float(getattr(config, "UI_SCALE", 1.0))
        ui_scale = max(1.0, min(ui_scale, 2.5))

        splash.destroy()

        ctk = loaded["ctk"]
        IgniteApp = loaded["IgniteApp"]

        ctk.set_appearance_mode("light")

        try:
            ctk.deactivate_automatic_dpi_awareness()
            ctk.set_widget_scaling(ui_scale)
            ctk.set_window_scaling(ui_scale)
        except Exception as e:
            logging.debug(f"UI-Skalierung konnte nicht gesetzt werden: {e}")

        root = ctk.CTk()
        
        try:
            root.tk.call('tk', 'scaling', (96.0 * ui_scale) / 72.0)
        except Exception as e:
            logging.debug(f"tk scaling konnte nicht gesetzt werden: {e}")

        app = IgniteApp(root)
        root.mainloop()

    # Background-Thread starten
    t = threading.Thread(target=load_heavy, daemon=True)
    t.start()

    # Tkinter-Eventloop läuft bis _on_load_done() splash.destroy() aufruft
    splash.mainloop()


if __name__ == "__main__":
    main()
