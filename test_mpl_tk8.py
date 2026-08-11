import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

root = tk.Tk()
fig = Figure(figsize=(6, 3.8), dpi=100)
ax = fig.add_subplot(111)

import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False

# extremely long tick labels!
pixels_disp = [1.0000000000000000001, 1.0000000000000000002]
ax.hist(pixels_disp, bins=128)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def do_draw():
    try:
        canvas.draw()
        print("Draw successful with tiny range.")
    except Exception as e:
        print("Crash:", e)
    root.destroy()

root.after(100, do_draw)
root.mainloop()
