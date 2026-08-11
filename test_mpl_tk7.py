import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

root = tk.Tk()

fig = Figure(figsize=(6, 3.8), dpi=100)
ax = fig.add_subplot(111)

import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False

# We force a negative tick!
pixels_disp = [-10, 0, 10]
ax.plot(pixels_disp)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def do_draw():
    try:
        canvas.draw()
        print("Draw successful with negative tick.")
    except Exception as e:
        print("Crash:", e)
    root.destroy()

root.after(100, do_draw)
root.mainloop()
