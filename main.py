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
    """Erstellt einen modernen, hochauflösenden Medical Workstation Splash-Screen."""
    splash = tk.Tk()
    splash.title("IGNITE")
    splash.overrideredirect(True)
    splash.configure(bg="#0B0F19")
    splash.resizable(False, False)

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()

    if sw >= 3200 or sh >= 1800:
        W, H = 640, 390
        bar_w = 540
        bar_h = 6
    elif sw >= 2200 or sh >= 1300:
        W, H = 580, 360
        bar_w = 490
        bar_h = 6
    else:
        W, H = 540, 340
        bar_w = 460
        bar_h = 5

    x = (sw - W) // 2
    y = (sh - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")

    # Äußerer präziser Rahmen
    outer_border = tk.Frame(splash, bg="#1E293B", bd=1)
    outer_border.pack(fill=tk.BOTH, expand=True)

    inner_bg = tk.Frame(outer_border, bg="#0B0F19")
    inner_bg.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    # Oberer leuchtender Cyan/Indigo-Gradient-Streifen (3px)
    top_strip = tk.Canvas(inner_bg, height=3, bg="#0B0F19", highlightthickness=0, bd=0)
    top_strip.pack(fill=tk.X, side=tk.TOP)
    
    strip_w = W
    for i in range(strip_w):
        t = i / max(1, strip_w)
        if t < 0.5:
            f = t * 2.0
            r = int(2 + (56 - 2) * f)
            g = int(132 + (189 - 132) * f)
            b = int(199 + (248 - 199) * f)
        else:
            f = (t - 0.5) * 2.0
            r = int(56 + (99 - 56) * f)
            g = int(189 + (102 - 189) * f)
            b = int(248 + (241 - 248) * f)
        top_strip.create_line(i, 0, i, 3, fill=f"#{r:02x}{g:02x}{b:02x}")

    content = tk.Frame(inner_bg, bg="#0B0F19")
    content.pack(expand=True, fill=tk.BOTH, padx=28, pady=(18, 16))

    # Header-Bereich mit Logo und Titel
    header_frame = tk.Frame(content, bg="#0B0F19")
    header_frame.pack(fill=tk.X, pady=(0, 10))

    # Logo
    logo_path = _get_resource_path(os.path.join("icon", "LogoRund.png"))
    logo_img_ref = None
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path).resize((52, 52), Image.LANCZOS)
        logo_img_ref = ImageTk.PhotoImage(img)
        logo_label = tk.Label(header_frame, image=logo_img_ref, bg="#0B0F19")
        logo_label.pack(side=tk.LEFT, padx=(0, 16))
    except Exception as e:
        logo_label = tk.Label(header_frame, text="⚡", font=("Segoe UI", 24), fg="#38BDF8", bg="#0B0F19")
        logo_label.pack(side=tk.LEFT, padx=(0, 16))

    # Titel & Badges
    title_box = tk.Frame(header_frame, bg="#0B0F19")
    title_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    title_row = tk.Frame(title_box, bg="#0B0F19")
    title_row.pack(anchor="w")

    tk.Label(
        title_row,
        text="IGNITE",
        font=("Segoe UI", 22, "bold"),
        fg="#F8FAFC",
        bg="#0B0F19"
    ).pack(side=tk.LEFT)

    # Version Pill Badge
    badge_frame = tk.Frame(title_row, bg="#1E293B", bd=0, padx=6, pady=1)
    badge_frame.pack(side=tk.LEFT, padx=(10, 0), pady=4)
    tk.Label(
        badge_frame,
        text="v3.2.0 · Core",
        font=("Segoe UI", 8, "bold"),
        fg="#38BDF8",
        bg="#1E293B"
    ).pack()

    tk.Label(
        title_box,
        text="THERMOAI VISION · MEDICAL IMAGING SUITE",
        font=("Segoe UI", 8, "bold"),
        fg="#94A3B8",
        bg="#0B0F19"
    ).pack(anchor="w", pady=(1, 0))

    tk.Label(
        title_box,
        text="Jugend forscht 2026 · Fachgebiet Arbeitswelt",
        font=("Segoe UI", 8),
        fg="#64748B",
        bg="#0B0F19"
    ).pack(anchor="w")

    # Subsystem-Karten-Container (Detail-Anzeige)
    status_card = tk.Frame(content, bg="#131B2A", bd=1, highlightbackground="#1E293B", highlightthickness=1)
    status_card.pack(fill=tk.X, pady=(4, 10), ipady=6, ipadx=10)

    # Status-Kopfzeile mit Prozentanzeige
    status_header = tk.Frame(status_card, bg="#131B2A")
    status_header.pack(fill=tk.X, padx=4)

    status_var = tk.StringVar(value="System-Initialisierung...")
    tk.Label(
        status_header,
        textvariable=status_var,
        font=("Segoe UI", 10, "bold"),
        fg="#F1F5F9",
        bg="#131B2A"
    ).pack(side=tk.LEFT)

    percent_var = tk.StringVar(value="0%")
    tk.Label(
        status_header,
        textvariable=percent_var,
        font=("Consolas", 10, "bold"),
        fg="#38BDF8",
        bg="#131B2A"
    ).pack(side=tk.RIGHT)

    # Detaillierter Subsystem-Log-Text
    subsystem_var = tk.StringVar(value="[SYS] Starte Subsystem-Architektur...")
    tk.Label(
        status_card,
        textvariable=subsystem_var,
        font=("Consolas", 8),
        fg="#64748B",
        bg="#131B2A",
        anchor="w"
    ).pack(fill=tk.X, padx=4, pady=(2, 0))

    # Fortschrittsbalken Canvas mit Shimmer-Effekt
    pbar_canvas = tk.Canvas(
        content,
        width=bar_w,
        height=bar_h,
        bg="#1E293B",
        highlightthickness=0,
        bd=0
    )
    pbar_canvas.pack(fill=tk.X, pady=(0, 10))

    # Footer
    footer = tk.Frame(content, bg="#0B0F19")
    footer.pack(fill=tk.X, side=tk.BOTTOM)

    tk.Label(
        footer,
        text="© 2026 Jona Noack  ·  Forschungsprototyp  ·  Deterministic Lemire Morphology Pipeline",
        font=("Segoe UI", 7),
        fg="#475569",
        bg="#0B0F19"
    ).pack(side=tk.LEFT)

    # State für Animation & Shimmer
    splash._logo_ref = logo_img_ref
    splash._pbar_canvas = pbar_canvas
    splash._status_var = status_var
    splash._subsystem_var = subsystem_var
    splash._percent_var = percent_var
    splash._bar_w = bar_w
    splash._bar_h = bar_h
    splash._target_progress = 0.0
    splash._current_progress = 0.0
    splash._shimmer_pos = 0.0
    splash._anim_running = True

    def _anim_loop():
        if not splash._anim_running:
            return
        
        # Weiche Interpolation (Lerp)
        diff = splash._target_progress - splash._current_progress
        splash._current_progress += diff * 0.12
        if abs(diff) < 0.001:
            splash._current_progress = splash._target_progress

        curr_w = int(splash._bar_w * splash._current_progress)

        # Shimmer-Bewegung
        splash._shimmer_pos = (splash._shimmer_pos + 8.0)
        if splash._shimmer_pos > splash._bar_w + 60:
            splash._shimmer_pos = -60

        # Canvas rendern
        pbar_canvas.delete("all")
        pbar_canvas.create_rectangle(0, 0, splash._bar_w, splash._bar_h, fill="#1E293B", outline="")

        if curr_w > 0:
            pbar_canvas.create_rectangle(0, 0, curr_w, splash._bar_h, fill="#0284C7", outline="")

            # Shimmer-Glow Band berechnen
            sh_start = int(splash._shimmer_pos)
            sh_end = sh_start + 50

            clip_start = max(0, min(curr_w, sh_start))
            clip_end = max(0, min(curr_w, sh_end))

            if clip_end > clip_start:
                mid = (clip_start + clip_end) // 2
                pbar_canvas.create_rectangle(clip_start, 0, clip_end, splash._bar_h, fill="#38BDF8", outline="")
                if clip_end - clip_start > 10:
                    inner_start = max(clip_start, mid - 6)
                    inner_end = min(clip_end, mid + 6)
                    pbar_canvas.create_rectangle(inner_start, 0, inner_end, splash._bar_h, fill="#BAE6FD", outline="")

        pct = int(splash._current_progress * 100)
        splash._percent_var.set(f"{pct}%")

        splash.after(20, _anim_loop)

    splash.after(20, _anim_loop)
    return splash


def update_splash(splash, progress: float, message: str, subsystem_detail: str = ""):
    """Aktualisiert Ziel-Fortschrittsbalken, Status und Subsystem-Telemetrie im Splash."""
    try:
        splash._target_progress = min(1.0, max(0.0, progress))
        splash._status_var.set(message)
        if subsystem_detail:
            splash._subsystem_var.set(subsystem_detail)
        splash.update_idletasks()
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
        """Lädt alle schweren Abhängigkeiten schrittweise im Background-Thread mit Telemetrie."""
        try:
            import time
            import platform

            # Schritt 1: System- & Hardware-Check
            time.sleep(0.15)
            cpu_count = os.cpu_count() or 4
            splash.after(0, lambda: update_splash(
                splash,
                0.15,
                "Hardware-Erkennung & System-Check...",
                f"[SYS] {platform.machine()} · {cpu_count} CPU-Threads · DPI {_dpi_scale_for(splash)}x"
            ))

            # Schritt 2: Numerische Bibliotheken & Rust Core
            time.sleep(0.2)
            import numpy as np
            loaded["np"] = np

            rust_backend_str = "CPU-Rayon (4 Kerne)"
            try:
                import ignite_core
                loaded["ignite_core"] = ignite_core
                rust_backend_str = getattr(ignite_core, "__backend__", f"v{getattr(ignite_core, '__version__', '3.2.0')}")
            except Exception:
                pass

            splash.after(0, lambda: update_splash(
                splash,
                0.35,
                "Lade Rust FFI-Bindings & Rayon Core...",
                f"[RUST] ignite_core initialisiert · {rust_backend_str} bereit"
            ))

            # Schritt 3: Computer-Vision & Morphologie
            time.sleep(0.2)
            import image_processing
            loaded["image_processing"] = image_processing

            splash.after(0, lambda: update_splash(
                splash,
                0.55,
                "Initialisiere Lemire-Morphologie & Filterkerne...",
                "[CORE] O(K) separable Top-Hat & Chamfer-Distanztransformation aktiv"
            ))

            # Schritt 4: CustomTkinter & UI System
            time.sleep(0.2)
            import customtkinter as ctk
            loaded["ctk"] = ctk

            splash.after(0, lambda: update_splash(
                splash,
                0.72,
                "Lade CustomTkinter & Material 3 Design...",
                "[UI] Material 3 Design-System · Dark Mode · High-Contrast Theme"
            ))

            # Schritt 5: App-Architektur & Views
            time.sleep(0.2)
            from gui.main_window import IgniteApp
            loaded["IgniteApp"] = IgniteApp

            splash.after(0, lambda: update_splash(
                splash,
                0.88,
                "Lade Diagnostic Views & Analyse-Services...",
                "[GUI] Podologie-, Batch- und Analytics-Viewports geladen"
            ))

            # Schritt 6: System bereit
            time.sleep(0.2)
            splash.after(0, lambda: update_splash(
                splash,
                1.0,
                "System betriebsbereit.",
                "[READY] Alle Subsysteme verifiziert · Starte IGNITE Suite..."
            ))
            time.sleep(0.35)

        except Exception as e:
            error_holder["error"] = str(e)
        finally:
            splash.after(0, _on_load_done)

    def _on_load_done():
        """Wird im Haupt-Thread aufgerufen wenn Loading fertig ist."""
        splash._anim_running = False

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
