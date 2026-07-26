"""
generate_diagrams.py
Erzeugt wissenschaftliche Diagramme, Skizzen und Ablaufpläne für die Jugend forscht Arbeit.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

os.makedirs("images", exist_ok=True)

# Set global style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10

# ─────────────────────────────────────────────────────────────────────────────
# SKIZZE 1: Top-Hat-Prinzip (1D Temperaturprofil-Skizze)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4), dpi=300)

x = np.linspace(0, 10, 500)
# Original-Temperaturprofil mit langsamem Haltungswelle-Gradienten + scharfem Hotspot
background = 25.0 + 3.0 * np.sin(x / 2.0)
hotspot = 6.0 * np.exp(-((x - 6.5) ** 2) / (2 * 0.2**2))
original = background + hotspot

# Opening (glatter Hintergrund)
opening = background.copy()

# Top-Hat Differenz
tophat = original - opening
threshold = np.ones_like(x) * 2.5

ax.plot(x, original, 'r-', linewidth=2, label='Original-Temperaturprofil I(x)')
ax.plot(x, opening, 'b--', linewidth=2, label='Morphologisches Opening γ(I) (Hintergrund)')
ax.plot(x, tophat + 20.0, 'g-', linewidth=2, label='Top-Hat Differenz (verschoben)')
ax.axhline(y=22.5, color='orange', linestyle=':', linewidth=1.5, label='Schwellenwert μ + 3σ')

ax.fill_between(x, 22.5, tophat + 20.0, where=(tophat + 20.0 > 22.5), color='red', alpha=0.4, label='Erkannter Hotspot')

ax.set_title('Skizze 1: Prinzip der morphologischen Top-Hat-Transformation (1D-Profil)', fontsize=11, fontweight='bold')
ax.set_xlabel('Position auf dem Körper (x)')
ax.set_ylabel('Temperatur / Intensität')
ax.legend(loc='upper left', fontsize=8)
plt.tight_layout()
plt.savefig('images/skizze_tophat_prinzip.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# SKIZZE 2: Gauß vs. Robust-MAD bei bimodaler Verteilung (Kalte Zehen)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4), dpi=300)

# Bimodale Verteilung simulieren (Kalte Zehen Peak + Körper Peak)
np.random.seed(42)
cold_toes = np.random.normal(loc=15, scale=2, size=3000)
body_pixels = np.random.normal(loc=35, scale=3, size=7000)
bimodal_data = np.concatenate([cold_toes, body_pixels])

# Statistische Werte
mu = np.mean(bimodal_data)
sigma = np.std(bimodal_data)
gauss_thresh = mu + 2.0 * sigma

median = np.median(bimodal_data)
mad = np.median(np.abs(bimodal_data - median))
sigma_mad = 1.4826 * mad
mad_thresh = median + 2.0 * sigma_mad

ax.hist(bimodal_data, bins=60, color='gray', alpha=0.6, density=True, label='Temperaturverteilung (Gewebepixel)')
ax.axvline(mu, color='blue', linestyle='--', linewidth=2, label=f'Gauß-Mittelwert μ ({mu:.1f})')
ax.axvline(gauss_thresh, color='blue', linestyle='-', linewidth=2, label=f'Gauß-Schwelle μ+2σ ({gauss_thresh:.1f})')

ax.axvline(median, color='green', linestyle='--', linewidth=2, label=f'Median μ_tilde ({median:.1f})')
ax.axvline(mad_thresh, color='green', linestyle='-', linewidth=2, label=f'MAD-Schwelle ({mad_thresh:.1f})')

ax.set_title('Skizze 2: Vergleichende Statistik bei bimodaler Verteilung (kalte Zehen)', fontsize=11, fontweight='bold')
ax.set_xlabel('Temperaturwert (°C)')
ax.set_ylabel('Wahrscheinlichkeitsdichte')
ax.legend(loc='upper right', fontsize=8)
plt.tight_layout()
plt.savefig('images/skizze_gauss_vs_mad.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAMM 3: Geschwindigkeitsvergleich der Backends (Balkendiagramm)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4), dpi=300)

backends = ['PyTorch (CUDA GPU)', 'Mein Rust-Core (CPU)', 'Python Fallback (CPU)']
times_small = [8.2, 22.5, 78.4]
times_large = [18.4, 41.1, 210.6]

x = np.arange(len(backends))
width = 0.35

rects1 = ax.bar(x - width/2, times_small, width, label='Bildgröße 400 x 400', color='#4F46E5')
rects2 = ax.bar(x + width/2, times_large, width, label='Bildgröße 1440 x 1080', color='#06B6D4')

ax.set_ylabel('Ausführungszeit (Millisekunden)')
ax.set_title('Diagramm 1: Rechenzeiten der verschiedenen Backends im Vergleich', fontsize=11, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(backends)
ax.legend()

# Labeling bars
for rect in rects1 + rects2:
    height = rect.get_height()
    ax.annotate(f'{height:.1f}ms',
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom', fontsize=8)

plt.tight_layout()
plt.savefig('images/diagramm_rechenzeiten_vergleich.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# SKIZZE 4: Klinischer Behandlungsablauf (Workflow-Schaltplan)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 2.5), dpi=300)
ax.axis('off')

boxes = [
    ("1. Patient betritt\nBehandlungsraum", "#E2E8F0"),
    ("2. Wärmebild-Foto\nerstellen", "#CBD5E1"),
    ("3. IGNITE Analyse\n(< 30 ms local)", "#6366F1"),
    ("4. Visuelles Overlay\n& ΔT Warnung", "#38BDF8"),
    ("5. Ärztliche Diagnose\n& Behandlung", "#4ADE80")
]

for i, (text, color) in enumerate(boxes):
    rect = patches.FancyBboxPatch((i*2.0, 0.2), 1.6, 0.6, boxstyle="round,pad=0.1", 
                                  facecolor=color, edgecolor="black", linewidth=1)
    ax.add_patch(rect)
    text_color = "white" if color == "#6366F1" else "black"
    ax.text(i*2.0 + 0.8, 0.5, text, ha="center", va="center", fontsize=8, fontweight="bold", color=text_color)
    
    if i < len(boxes) - 1:
        ax.annotate("", xy=((i+1)*2.0 - 0.3, 0.5), xytext=(i*2.0 + 1.7, 0.5),
                    arrowprops=dict(arrowstyle="->", lw=2, color="#475569"))

ax.set_xlim(-0.2, 9.8)
ax.set_ylim(0, 1)
plt.title('Skizze 3: Integration von IGNITE in den klinischen Praxis-Workflow', fontsize=11, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig('images/skizze_praxis_workflow.png')
plt.close()

print("[+] Wissenschaftliche Skizzen und Diagramme in images/ erzeugt.")
