import tkinter as tk
import customtkinter as ctk
import sys

root = tk.Tk()
print("Platform:", sys.platform)
print("tk scaling:", root.tk.call('tk', 'scaling'))
print("winfo_fpixels('1i'):", root.winfo_fpixels('1i'))
print("ctk scaling:", ctk.ScalingTracker.get_widget_scaling(root))
