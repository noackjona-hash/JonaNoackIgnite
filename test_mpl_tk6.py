import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib

root = tk.Tk()

fig = Figure(figsize=(6, 3.8), dpi=100)
ax = fig.add_subplot(111)

# Generate a HUGE LIST
import random
pixels_disp = [random.uniform(20.0, 40.0) for _ in range(300000)]
mean_disp = 30.0
thresh_disp = 35.0
unit_str = "C"

ax.hist(pixels_disp, bins=128, color="#0078D4", alpha=0.7, edgecolor="none")
ax.axvline(mean_disp, color="#F4F4F5", linestyle="--", linewidth=1.5)
ax.axvline(thresh_disp, color="#C42B1C", linestyle="-.", linewidth=2.0)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def do_draw():
    try:
        canvas.draw()
        print("Draw successful with LIST.")
    except Exception as e:
        print("Crash with LIST:", e)
    root.destroy()

root.after(100, do_draw)
root.mainloop()
