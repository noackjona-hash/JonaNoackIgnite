import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False

root = tk.Tk()

fig = Figure(figsize=(6, 3.8), dpi=120, facecolor="#18181B")
ax = fig.add_subplot(111, facecolor="#09090B")

pixels_disp = np.random.uniform(20.0, 40.0, 300000)
mean_disp = 30.0
thresh_disp = 35.0
unit_str = "C"

ax.hist(pixels_disp, bins=128, color="#0078D4", alpha=0.7, edgecolor="none")
ax.axvline(mean_disp, color="#F4F4F5", linestyle="--", linewidth=1.5)
ax.axvline(thresh_disp, color="#C42B1C", linestyle="-.", linewidth=2.0)

ax.set_xlabel("Temperatur (C)", fontsize=9, fontweight="bold")
ax.set_ylabel("Haeufigkeit", fontsize=9, fontweight="bold")
ax.grid(True)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def do_draw():
    try:
        canvas.draw()
        print("Draw successful inside after callback.")
    except Exception as e:
        print("Crash:", e)
    root.destroy()

root.after(100, do_draw)
root.mainloop()
