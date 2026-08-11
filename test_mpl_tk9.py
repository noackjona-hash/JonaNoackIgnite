import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False

root = tk.Tk()

try:
    fig = Figure(figsize=(6, 3.8), dpi=1)
    ax = fig.add_subplot(111)
    ax.hist([1, 2, 3], bins=3)
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.draw()
    print("DPI=1 successful")
except Exception as e:
    print("DPI=1 crash:", e)

try:
    fig = Figure(figsize=(6, 3.8), dpi=0)
    ax = fig.add_subplot(111)
    ax.hist([1, 2, 3], bins=3)
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.draw()
    print("DPI=0 successful")
except Exception as e:
    print("DPI=0 crash:", e)
