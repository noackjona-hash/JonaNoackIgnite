import os
import sys
import threading
import logging

# Windows: Tcl/Tk-Pfade für Tkinter / CustomTkinter in venvs automatisch konfigurieren
if sys.platform.startswith("win"):
    base_tcl = os.path.join(sys.base_prefix, "tcl")
    if os.path.exists(base_tcl):
        for item in os.listdir(base_tcl):
            if item.startswith("tcl8.") and "TCL_LIBRARY" not in os.environ:
                os.environ["TCL_LIBRARY"] = os.path.join(base_tcl, item)
            elif item.startswith("tk8.") and "TK_LIBRARY" not in os.environ:
                os.environ["TK_LIBRARY"] = os.path.join(base_tcl, item)

import tkinter as tk

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
    """Erstellt einen klaren, professionellen Workstation Splash-Screen."""
    splash = tk.Tk()
    splash.title("IGNITE")
    splash.overrideredirect(True)
    splash.configure(bg="#0F172A")
    splash.resizable(False, False)

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()

    if sw >= 3200 or sh >= 1800:
        W, H = 640, 380
        bar_w = 420
    elif sw >= 2200 or sh >= 1300:
        W, H = 560, 340
        bar_w = 380
    else:
        W, H = 500, 310
        bar_w = 340

    x = (sw - W) // 2
    y = (sh - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")

    # Äußerer zarter Rahmen
    border_frame = tk.Frame(splash, bg="#334155", bd=1)
    border_frame.pack(fill=tk.BOTH, expand=True)

    inner_bg = tk.Frame(border_frame, bg="#0F172A")
    inner_bg.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    content = tk.Frame(inner_bg, bg="#0F172A")
    content.pack(expand=True, padx=20, pady=20)

    # Logo
    logo_path = _get_resource_path(os.path.join("icon", "LogoRund.png"))
    logo_img_ref = None
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path).resize((56, 56), Image.LANCZOS)
        logo_img_ref = ImageTk.PhotoImage(img)
        tk.Label(content, image=logo_img_ref, bg="#0F172A").pack(pady=(0, 8))
    except Exception as e:
        logging.debug(f"Fehler beim Laden des Splash-Logos: {e}")
        tk.Label(content, text="", bg="#0F172A", height=1).pack()

    # Titel
    tk.Label(
        content,
        text="IGNITE",
        font=("Segoe UI", 28, "bold"),
        fg="#F8FAFC",
        bg="#0F172A"
    ).pack()

    tk.Label(
        content,
        text="Medical Imaging Suite  ·  Jugend forscht 2026",
        font=("Segoe UI", 11),
        fg="#94A3B8",
        bg="#0F172A"
    ).pack(pady=(2, 14))

    status_var = tk.StringVar(value="Initialisierung…")
    tk.Label(
        content,
        textvariable=status_var,
        font=("Segoe UI", 11),
        fg="#64748B",
        bg="#0F172A"
    ).pack(pady=(0, 8))

    # Fortschrittsbalken
    pbar_canvas = tk.Canvas(
        content,
        width=bar_w,
        height=4,
        bg="#1E293B",
        highlightthickness=0,
        bd=0
    )
    pbar_canvas.pack()
    bar = pbar_canvas.create_rectangle(0, 0, 0, 4, fill="#0284C7", outline="")

    tk.Label(
        content,
        text="© 2026 Jona Noack  ·  Fachgebiet Arbeitswelt",
        font=("Segoe UI", 10),
        fg="#475569",
        bg="#0F172A"
    ).pack(pady=(14, 0))

    splash._logo_ref = logo_img_ref
    splash._pbar_canvas = pbar_canvas
    splash._pbar_bar = bar
    splash._status_var = status_var
    splash._pbar_width = bar_w
    splash._pbar_height = 4

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

            splash.after(0, lambda: update_splash(splash, 0.85, "Lade Benutzeroberfläche…"))

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

        ctk.set_appearance_mode("system")

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
