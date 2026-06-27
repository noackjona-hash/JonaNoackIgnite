import customtkinter as ctk
from gui import IgniteApp

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    app = IgniteApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
