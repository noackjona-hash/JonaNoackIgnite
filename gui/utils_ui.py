import customtkinter as ctk
from gui.theme import *

def make_slider(master, label_text, from_, to, default_val, resolution=0.01):
    """Erstellt ein Steuerelement mit Slider und dynamischer Werteanzeige."""
    frame = ctk.CTkFrame(master, fg_color="transparent")
    frame.pack(fill=ctk.X, pady=6)
    
    top_row = ctk.CTkFrame(frame, fg_color="transparent")
    top_row.pack(fill=ctk.X)
    
    lbl_title = ctk.CTkLabel(top_row, text=label_text, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
    lbl_title.pack(side=ctk.LEFT)
    
    val_lbl = ctk.CTkLabel(top_row, text=str(default_val), font=ctk.CTkFont(size=11), text_color=COLOR_PRIMARY_ACCENT)
    val_lbl.pack(side=ctk.RIGHT)
    
    slider = ctk.CTkSlider(
        frame, 
        from_=from_, 
        to=to, 
        number_of_steps=int((to - from_)/resolution), 
        fg_color=COLOR_BORDER_CARD, 
        progress_color=COLOR_PRIMARY_ACCENT, 
        button_color=COLOR_PRIMARY_ACCENT,
        button_hover_color=COLOR_HOVER_ACCENT
    )
    slider.set(default_val)
    slider.pack(fill=ctk.X, pady=2)
    
    return slider, val_lbl
