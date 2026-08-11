import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False

root = tk.Tk()
fig = Figure(figsize=(6, 3.8), dpi=120)
ax = fig.add_subplot(111)

# All identical values!
pixels_disp = np.full(10000, 25.0)
ax.hist(pixels_disp, bins=128)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.draw()
print("Draw successful with uniform data.")
