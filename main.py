# -*- coding: utf-8 -*-
"""main.py – IGNITE Medical Imaging Suite bootloader."""

import tkinter as tk
import threading
import os
import logging

# ─── Sofortiger Splash-Screen ─────────────────────────────────────────────────
# Öffnet sich BEVOR schwere Imports geladen werden.

def _get_resource_path(relative_path: str) -> str:
    import sys
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def _enable_dpi_awareness() -> None:
    """Aktiviert unter Windows die DPI-Awareness des Prozesses."""
    import sys
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception as e:
            logging.debug(f"DPI-Awareness konnte nicht gesetzt werden: {e}")


def _dpi_scale_for(win) -> float:
    """Ermittelt den DPI-Skalierungsfaktor fuer ein Fenster."""
    try:
        return max(1.0, round(win.winfo_fpixels("1i") / 96.0, 2))
    except Exception:
        return 1.0


def create_instant_splash():
    """Erstellt einen eleganten, großzügigen Google-Style Splash-Screen."""
    splash = tk.Tk()
    splash.title("IGNITE")
    splash.overrideredirect(True)
    splash.configure(bg="#FFFFFF")
    splash.resizable(False, False)

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()

    # Großzügige Dimensionen passend zur Bildschirmauflösung
    if sw >= 3200 or sh >= 1800:
        W, H = 680, 420
        bar_w = 460
    elif sw >= 2200 or sh >= 1300:
        W, H = 600, 380
        bar_w = 420
    else:
        W, H = 540, 350
        bar_w = 380

    x = (sw - W) // 2
    y = (sh - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")

    # Äußerer zarter Rahmen
    border_frame = tk.Frame(splash, bg="#E1E3E1", bd=1)
    border_frame.pack(fill=tk.BOTH, expand=True)

    inner_bg = tk.Frame(border_frame, bg="#FFFFFF")
    inner_bg.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    content = tk.Frame(inner_bg, bg="#FFFFFF")
    content.pack(expand=True, padx=24, pady=24)

    # Logo
    logo_path = _get_resource_path(os.path.join("icon", "LogoRund.png"))
    logo_img_ref = None
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path).resize((72, 72), Image.LANCZOS)
        logo_img_ref = ImageTk.PhotoImage(img)
        tk.Label(content, image=logo_img_ref, bg="#FFFFFF").pack(pady=(0, 10))
    except Exception as e:
        logging.debug(f"Fehler beim Laden des Splash-Logos: {e}")
        tk.Label(content, text="", bg="#FFFFFF", height=2).pack()

    # Titel
    tk.Label(
        content,
        text="IGNITE",
        font=("Segoe UI", 36, "bold"),
        fg="#1F1F1F",
        bg="#FFFFFF"
    ).pack()

    tk.Label(
        content,
        text="Medical Imaging Suite  ·  Jugend forscht 2026",
        font=("Segoe UI", 13),
        fg="#5F6368",
        bg="#FFFFFF"
    ).pack(pady=(2, 16))

    status_var = tk.StringVar(value="Wird initialisiert…")
    tk.Label(
        content,
        textvariable=status_var,
        font=("Segoe UI", 12),
        fg="#727775",
        bg="#FFFFFF"
    ).pack(pady=(0, 10))

    # Fortschrittsbalken
    pbar_canvas = tk.Canvas(
        content,
        width=bar_w,
        height=6,
        bg="#E9EEF6",
        highlightthickness=0,
        bd=0
    )
    pbar_canvas.pack()
    bar = pbar_canvas.create_rectangle(0, 0, 0, 6, fill="#0B57D0", outline="")

    tk.Label(
        content,
        text="© 2026 Jona Noack  ·  Fachgebiet Arbeitswelt",
        font=("Segoe UI", 11),
        fg="#8E918F",
        bg="#FFFFFF"
    ).pack(pady=(16, 0))

    splash._logo_ref = logo_img_ref
    splash._pbar_canvas = pbar_canvas
    splash._pbar_bar = bar
    splash._status_var = status_var
    splash._pbar_width = bar_w
    splash._pbar_height = 6

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

    _enable_dpi_awareness()

    splash = create_instant_splash()
    splash.update()

    loaded = {}
    error_holder = {}

    def load_heavy():
        """Lädt alle schweren Abhängigkeiten im Background-Thread."""
        try:
            splash.after(0, lambda: update_splash(splash, 0.25, "Lade Bildverarbeitung…"))

            import customtkinter as ctk
            loaded["ctk"] = ctk

            splash.after(0, lambda: update_splash(splash, 0.55, "Initialisiere Hardware-Backend…"))

            from gui.main_window import IgniteApp
            loaded["IgniteApp"] = IgniteApp

            splash.after(0, lambda: update_splash(splash, 0.85, "Lade Google Fluid Design…"))

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

        # Responsive Skalierung für High-DPI Displays (z.B. 1440p / 4K)
        if sw >= 3200 or sh >= 1800:
            auto_scale = 1.40
        elif sw >= 2200 or sh >= 1300:
            auto_scale = 1.20
        elif sw >= 1800:
            auto_scale = 1.10
        else:
            auto_scale = 1.0

        user_scale = float(getattr(config, "UI_SCALE", 1.0))
        ui_scale = auto_scale * user_scale
        ui_scale = max(1.0, min(ui_scale, 2.2))

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
        app = IgniteApp(root)
        root.mainloop()

    t = threading.Thread(target=load_heavy, daemon=True)
    t.start()

    splash.mainloop()


if __name__ == "__main__":
    main()
