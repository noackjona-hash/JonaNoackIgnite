import customtkinter as ctk
from gui import IgniteApp, APP_VERSION, get_resource_path
from PIL import Image
import os
import time


def show_splash(duration_ms: int = 2200) -> None:
    """Zeigt einen professionellen Splash Screen beim Start der Anwendung."""
    splash = ctk.CTk()
    splash.title("IGNITE")
    splash.geometry("480x280")
    splash.resizable(False, False)
    splash.configure(fg_color="#09090B")
    splash.overrideredirect(True)  # Fenster ohne Rahmen

    # Fenster zentrieren
    splash.update_idletasks()
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw // 2) - 240
    y = (sh // 2) - 140
    splash.geometry(f"480x280+{x}+{y}")

    # Logo
    icon_png_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
    if os.path.exists(icon_png_path):
        try:
            logo_img = Image.open(icon_png_path)
            logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(64, 64))
            logo_lbl = ctk.CTkLabel(splash, image=logo_ctk, text="")
            logo_lbl.pack(pady=(36, 8))
        except Exception:
            ctk.CTkLabel(splash, text="", height=72).pack()
    else:
        ctk.CTkLabel(splash, text="", height=72).pack()

    # App-Name
    ctk.CTkLabel(
        splash,
        text="IGNITE",
        font=ctk.CTkFont(family="Arial", size=30, weight="bold"),
        text_color="#FAF5FF"
    ).pack(pady=(0, 2))

    ctk.CTkLabel(
        splash,
        text=f"Medical Imaging Suite  ·  v{APP_VERSION}",
        font=ctk.CTkFont(family="Arial", size=11),
        text_color="#71717A"
    ).pack(pady=(0, 18))

    # Trennlinie
    sep = ctk.CTkFrame(splash, fg_color="#27272A", height=1)
    sep.pack(fill=ctk.X, padx=40, pady=(0, 14))

    # Status-Label
    status_lbl = ctk.CTkLabel(
        splash,
        text="Initialisiere Backend...",
        font=ctk.CTkFont(family="Arial", size=11),
        text_color="#52525B"
    )
    status_lbl.pack(pady=(0, 4))

    # Copyright
    ctk.CTkLabel(
        splash,
        text=f"© 2026 Jona Noack  ·  Jugend forscht",
        font=ctk.CTkFont(family="Arial", size=9),
        text_color="#27272A"
    ).pack(pady=(0, 12))

    # Fortschrittsbalken
    pbar = ctk.CTkProgressBar(splash, width=340, height=3, fg_color="#18181B", progress_color="#06B6D4", corner_radius=2)
    pbar.set(0.0)
    pbar.pack(pady=(0, 0))

    steps = [
        (0.3, "Lade Konfiguration...", 300),
        (0.6, "Prüfe Backend-Verfügbarkeit...", 500),
        (0.85, "Initialisiere Benutzeroberfläche...", 600),
        (1.0, "Bereit.", 800),
    ]

    def animate(step_idx=0):
        if step_idx < len(steps):
            val, msg, delay = steps[step_idx]
            pbar.set(val)
            status_lbl.configure(text=msg)
            splash.after(delay, lambda: animate(step_idx + 1))
        else:
            splash.after(200, splash.destroy)

    splash.after(100, animate)
    splash.mainloop()


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Splash Screen anzeigen
    show_splash()

    # Hauptfenster starten
    root = ctk.CTk()
    app = IgniteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
