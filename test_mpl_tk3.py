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
ax.axvline(mean_disp, color="#F4F4F5", linestyle="--", linewidth=1.5,
           label=f"Mittelwert ({mean_disp:.1f} {unit_str})")
ax.axvline(thresh_disp, color="#C42B1C", linestyle="-.", linewidth=2.0,
           label=f"Grenzwert ({thresh_disp:.1f} {unit_str})")

color_spine = "#27272A"
color_tick = "#A1A1AA"
color_text = "#F4F4F5"
bg_legend = "#18181B"

ax.spines['bottom'].set_color(color_spine)
ax.spines['top'].set_color(color_spine)
ax.spines['left'].set_color(color_spine)
ax.spines['right'].set_color(color_spine)
ax.tick_params(colors=color_tick, labelsize=8)
ax.set_xlabel(f"Temperatur ({unit_str})", color=color_text, fontsize=9, fontweight="bold")
ax.set_ylabel("Haeufigkeit", color=color_text, fontsize=9, fontweight="bold")
ax.legend(facecolor=bg_legend, edgecolor=color_spine, labelcolor=color_text, fontsize=8)
ax.grid(color="#27272A", linestyle=":", linewidth=0.5)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.draw()
print("Draw successful with exact mimic.")
