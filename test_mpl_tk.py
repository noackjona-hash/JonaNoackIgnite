import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

root = tk.Tk()
print("Default tk scaling:", root.tk.call('tk', 'scaling'))

# Try to simulate the environment
fig = Figure(figsize=(6, 3.8), dpi=120)
ax = fig.add_subplot(111)

import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False

# Fake data
pixels_disp = np.random.normal(25, 5, 10000)
ax.hist(pixels_disp, bins=128)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.draw()
print("Draw successful.")
