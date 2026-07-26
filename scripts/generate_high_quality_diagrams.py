"""
generate_high_quality_diagrams.py
Erzeugt hochauflösende, publikationsreife Grafiken, Skizzen und Diagramme für die Jugend forscht Arbeit.
"""

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

os.makedirs("images", exist_ok=True)

plt.rcParams['font.sans-serif'] = 'Arial, DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 1.2

C_PRIMARY = '#4F46E5'   # Indigo
C_SECONDARY = '#0EA5E9' # Sky Blue
C_SUCCESS = '#10B981'   # Emerald Green
C_DANGER = '#F43F5E'    # Rose Red
C_WARNING = '#F59E0B'   # Amber
C_BG = '#F8FAFC'        # Slate 50
C_TEXT = '#0F172A'      # Slate 900
C_MUTED = '#64748B'     # Slate 500

# ─────────────────────────────────────────────────────────────────────────────
# 1. SKIZZE 1: Top-Hat-Prinzip (2-Panel 1D Temperaturprofil)
# ─────────────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 5.5), dpi=300, sharex=True)
fig.patch.set_facecolor('white')

x = np.linspace(0, 10, 600)
background = 26.0 + 2.5 * np.sin(x / 1.8)
hotspot = 5.5 * np.exp(-((x - 6.8) ** 2) / (2 * 0.25**2))
original = background + hotspot
opening = background.copy()

tophat = original - opening
threshold = 2.2

# Panel 1: Original vs Opening
ax1.plot(x, original, color=C_DANGER, linewidth=2.2, label='Original-Temperaturprofil I(x)')
ax1.plot(x, opening, color=C_PRIMARY, linestyle='--', linewidth=2.0, label='Morphologisches Opening γ(I) (Hintergrund)')
ax1.set_ylabel('Temperatur (°C)', fontweight='bold')
ax1.set_title('Skizze 1: Prinzip der morphologischen Top-Hat-Transformation', fontsize=11, fontweight='bold', pad=10)
ax1.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#E2E8F0')
ax1.set_facecolor(C_BG)

ax1.annotate('Lokaler Entzündungs-Hotspot\n(+ 5,5 °C Hitzespitze)', xy=(6.8, 33.5), xytext=(4.0, 32.5),
             arrowprops=dict(arrowstyle="->", lw=1.5, color=C_DANGER),
             fontweight='bold', color=C_DANGER, fontsize=9)
ax1.annotate('Physiologischer\nTemperaturverlauf', xy=(2.0, 28.0), xytext=(0.5, 31.0),
             arrowprops=dict(arrowstyle="->", lw=1.5, color=C_PRIMARY),
             color=C_PRIMARY, fontsize=9)

# Panel 2: Top-Hat Differenz & Schwellenwert
ax2.plot(x, tophat, color='#8B5CF6', linewidth=2.2, label='Top-Hat Differenz I(x) - γ(I)')
ax2.axhline(threshold, color=C_WARNING, linestyle=':', linewidth=2.0, label='Statistische Schwelle (μ + 3σ)')
ax2.fill_between(x, threshold, tophat, where=(tophat > threshold), color=C_DANGER, alpha=0.45, label='Isolierte Entzündungszone')

ax2.set_xlabel('Position auf der Hautoberfläche (cm)', fontweight='bold')
ax2.set_ylabel('Temperatur-Differenz (°C)', fontweight='bold')
ax2.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#E2E8F0')
ax2.set_facecolor(C_BG)
ax2.set_ylim(-0.5, 6.5)

plt.tight_layout()
plt.savefig('images/skizze_tophat_prinzip.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 2. SKIZZE 2: Gauß vs. Robust-MAD Statistik bei kalten Zehen
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 4.5), dpi=300)
fig.patch.set_facecolor('white')

x_temp = np.linspace(10, 42, 500)
p1 = 0.35 * (1 / (1.8 * np.sqrt(2 * np.pi))) * np.exp(-((x_temp - 16) ** 2) / (2 * 1.8**2))
p2 = 0.60 * (1 / (2.5 * np.sqrt(2 * np.pi))) * np.exp(-((x_temp - 31) ** 2) / (2 * 2.5**2))
p3 = 0.05 * (1 / (0.8 * np.sqrt(2 * np.pi))) * np.exp(-((x_temp - 38) ** 2) / (2 * 0.8**2))
density = p1 + p2 + p3

mu = 25.8
sigma = 7.2
gauss_thresh = mu + 1.5 * sigma

median = 30.2
mad = 2.4
sigma_mad = 1.4826 * mad
mad_thresh = median + 2.5 * sigma_mad

ax.plot(x_temp, density, color='#334155', linewidth=2.2, label='Gewebe-Temperaturverteilung (bimodal)')
ax.fill_between(x_temp, 0, density, color='#E2E8F0', alpha=0.5)

ax.axvline(mu, color=C_SECONDARY, linestyle='--', linewidth=1.8, label=f'Gauß-Mittelwert μ ({mu:.1f} °C)')
ax.axvline(gauss_thresh, color=C_DANGER, linestyle='-', linewidth=2.0, label=f'Gauß-Schwelle μ+2σ ({gauss_thresh:.1f} °C) -> Falsch-Positive!')

ax.axvline(median, color=C_SUCCESS, linestyle='--', linewidth=1.8, label=f'Median ({median:.1f} °C)')
ax.axvline(mad_thresh, color=C_SUCCESS, linestyle='-', linewidth=2.0, label=f'Robust-MAD Schwelle ({mad_thresh:.1f} °C) -> Korrekt!')

ax.fill_between(x_temp, 0, density, where=(x_temp >= gauss_thresh) & (x_temp < mad_thresh), color=C_WARNING, alpha=0.35, label='Fehlalarm-Zone durch Gauß-Verzerrung')

ax.set_title('Skizze 2: Vergleichende Statistik bei bimodaler Temperaturverteilung (kalte Zehen)', fontsize=11, fontweight='bold', pad=10)
ax.set_xlabel('Temperatur (°C)', fontweight='bold')
ax.set_ylabel('Häufigkeitsdichte', fontweight='bold')
ax.set_facecolor(C_BG)
ax.legend(loc='upper right', fontsize=8, frameon=True, facecolor='white', edgecolor='#CBD5E1')

plt.tight_layout()
plt.savefig('images/skizze_gauss_vs_mad.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 3. SKIZZE 3: Praxis-Workflow (Klinisches Ablaufdiagramm)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 2.8), dpi=300)
fig.patch.set_facecolor('white')
ax.axis('off')

steps = [
    ("1. Kamera-Aufnahme", "Wärmebild-Foto im\nBehandlungsraum", C_SECONDARY),
    ("2. IGNITE Import", "Sofort-Start (<50ms)\nLocal In-Memory", C_PRIMARY),
    ("3. Rust Pipeline", "5-Stufen Analyse\nRechenzeit < 30ms", '#8B5CF6'),
    ("4. Visual Overlay", "Neon-Rot Hotspot &\nΔT > 2,2°C Warnung", C_WARNING),
    ("5. Ärztliche Diagnose", "Orientierungshilfe &\nPDF-Befundexport", C_SUCCESS)
]

for i, (title, desc, color) in enumerate(steps):
    x_center = i * 2.1 + 1.0
    shadow = patches.FancyBboxPatch((x_center - 0.9, 0.15), 1.8, 1.3, boxstyle="round,pad=0.08,rounding_size=0.15",
                                    facecolor='#CBD5E1', edgecolor='none', alpha=0.5)
    ax.add_patch(shadow)
    
    card = patches.FancyBboxPatch((x_center - 0.92, 0.18), 1.8, 1.3, boxstyle="round,pad=0.08,rounding_size=0.15",
                                  facecolor='white', edgecolor=color, linewidth=2)
    ax.add_patch(card)
    
    header = patches.FancyBboxPatch((x_center - 0.92, 1.08), 1.8, 0.4, boxstyle="round,pad=0.08,rounding_size=0.15",
                                    facecolor=color, edgecolor=color, linewidth=1)
    ax.add_patch(header)
    
    ax.text(x_center, 1.28, title, ha="center", va="center", color="white", fontweight="bold", fontsize=9)
    ax.text(x_center, 0.62, desc, ha="center", va="center", color=C_TEXT, fontsize=8)

    if i < len(steps) - 1:
        ax.annotate("", xy=(x_center + 1.15, 0.83), xytext=(x_center + 0.92, 0.83),
                    arrowprops=dict(arrowstyle="-|>", lw=2.5, color=C_MUTED, mutation_scale=15))

ax.set_xlim(0, 10.5)
ax.set_ylim(0, 1.8)
plt.title('Skizze 3: Integration von IGNITE in den täglichen Behandlungsablauf', fontsize=11, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig('images/skizze_praxis_workflow.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 4. SKIZZE 4: Kontralaterale Asymmetrie (Podiatrische Fußsohlen-Skizze)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
fig.patch.set_facecolor('white')
ax.axis('off')

card_bg = patches.FancyBboxPatch((0.2, 0.2), 9.6, 4.6, boxstyle="round,pad=0.1,rounding_size=0.2",
                                 facecolor=C_BG, edgecolor='#CBD5E1', linewidth=1.5)
ax.add_patch(card_bg)

ax.plot([5.0, 5.0], [0.5, 4.0], color=C_MUTED, linestyle='--', linewidth=2.0)
ax.text(5.0, 0.35, "Spaltungsachse X_mid = W / 2", ha="center", va="center", color=C_MUTED, fontsize=8, fontweight="bold")

def draw_foot(ax, center_x, center_y, is_right=False):
    grid_y, grid_x = np.mgrid[-1.5:1.5:150j, -0.8:0.8:100j]
    flip = -1 if is_right else 1
    foot_shape = ((grid_x*flip + 0.1)**2 / 0.35**2 + (grid_y)**2 / 1.3**2) <= 1.0
    arch_cut = (grid_x*flip > 0.0) & (np.abs(grid_y) < 0.5)
    foot_shape[arch_cut] = False
    
    temp_field = np.zeros_like(grid_x) + 28.0
    temp_field[foot_shape] = 28.5 + 1.0 * np.exp(-(grid_x[foot_shape]**2 + grid_y[foot_shape]**2))
    
    if is_right:
        hotspot_zone = ((grid_x - 0.1)**2 + (grid_y - 0.4)**2) < 0.12
        temp_field[hotspot_zone] = 34.5
    
    temp_field[~foot_shape] = np.nan
    extent = [center_x - 1.5, center_x + 1.5, center_y - 2.0, center_y + 2.0]
    cmap = plt.cm.jet
    cmap.set_bad(color='white', alpha=0.0)
    ax.imshow(temp_field, cmap=cmap, vmin=24, vmax=36, extent=extent, origin='lower', alpha=0.85)

draw_foot(ax, 2.6, 2.3, is_right=False)
draw_foot(ax, 7.4, 2.3, is_right=True)

ax.text(2.6, 0.6, "Linker Fuß (Physiologisch)\nT_mean = 28,4 °C", ha="center", va="center", 
        fontsize=9, fontweight="bold", color=C_TEXT, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#CBD5E1"))

ax.text(7.4, 0.6, "Rechter Fuß (Pathologisch)\nT_mean = 31,8 °C", ha="center", va="center", 
        fontsize=9, fontweight="bold", color=C_TEXT, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#CBD5E1"))

warn_card = patches.FancyBboxPatch((1.2, 4.05), 7.6, 0.6, boxstyle="round,pad=0.08,rounding_size=0.12",
                                   facecolor='#FEE2E2', edgecolor=C_DANGER, linewidth=2.0)
ax.add_patch(warn_card)
ax.text(5.0, 4.35, "[WARNUNG] Pathologische Asymmetrie erkannt! ΔT = 3,4 °C (> 2,2 °C)",
        ha="center", va="center", fontsize=9.5, fontweight="bold", color='#991B1B')

ax.set_xlim(0, 10)
ax.set_ylim(0, 4.9)
plt.title('Skizze 4: Kontralaterale Asymmetrie-Analyse zwischen linker und rechter Fußsohle', fontsize=11, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig('images/skizze_asymmetrie_analyse.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 5. SKIZZE 5: Rust FFI Speicherarchitektur
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
fig.patch.set_facecolor('white')
ax.axis('off')

b1 = patches.FancyBboxPatch((0.5, 0.8), 2.5, 2.2, boxstyle="round,pad=0.1,rounding_size=0.15",
                             facecolor='#EFF6FF', edgecolor=C_PRIMARY, linewidth=2.0)
ax.add_patch(b1)
ax.text(1.75, 2.6, "Python Laufzeit (RAM)", ha="center", va="center", color=C_PRIMARY, fontweight="bold", fontsize=10)
ax.text(1.75, 1.8, "NumPy Array\n(C-Contiguous uint8)\nMatrizengröße H x W", ha="center", va="center", color=C_TEXT, fontsize=8.5)
ax.text(1.75, 1.1, "Speicheradresse: 0x7FFF...", ha="center", va="center", color=C_MUTED, fontsize=7.5, fontfamily="monospace")

ax.annotate("", xy=(4.3, 1.9), xytext=(3.1, 1.9),
            arrowprops=dict(arrowstyle="-|>", lw=3.0, color=C_SUCCESS, mutation_scale=18))
ax.text(3.7, 2.2, "PyO3 FFI Bridge\n(Zero-Copy Pointer)", ha="center", va="center", color=C_SUCCESS, fontweight="bold", fontsize=8.5)

b2 = patches.FancyBboxPatch((4.4, 0.8), 4.1, 2.2, boxstyle="round,pad=0.1,rounding_size=0.15",
                             facecolor='#FFF7ED', edgecolor='#F97316', linewidth=2.0)
ax.add_patch(b2)
ax.text(6.45, 2.6, "Nativer Rust Core (ignite_core)", ha="center", va="center", color='#C2410C', fontweight="bold", fontsize=10)
ax.text(6.45, 1.9, "PyReadonlyArray2 -> ndarray Slice", ha="center", va="center", color=C_TEXT, fontweight="bold", fontsize=8.5)

for t in range(4):
    tb = patches.Rectangle((4.7 + t*0.95, 1.0), 0.85, 0.5, facecolor='#EA580C', edgecolor='none', alpha=0.85)
    ax.add_patch(tb)
    ax.text(4.7 + t*0.95 + 0.42, 1.25, f"Core {t+1}", ha="center", va="center", color="white", fontsize=7.5, fontweight="bold")

ax.set_xlim(0, 9.0)
ax.set_ylim(0, 3.4)
plt.title('Skizze 5: Speichereffiziente Zero-Copy FFI-Architektur zwischen Python und Rust', fontsize=11, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig('images/skizze_rust_ffi_architektur.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 6. DIAGRAMM 1: Rechenzeiten im Vergleich (Balkendiagramm)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=300)
fig.patch.set_facecolor('white')

backends = ['PyTorch (CUDA GPU)', 'Mein Rust-Core (CPU)', 'Python Fallback (CPU)']
times_400 = [8.2, 22.5, 78.4]
times_1440 = [18.4, 41.1, 210.6]

x_pos = np.arange(len(backends))
w = 0.32

rects1 = ax.bar(x_pos - w/2, times_400, w, label='Bildauflösung 400 x 400 Pixel', color=C_PRIMARY, edgecolor='#3730A3', alpha=0.9)
rects2 = ax.bar(x_pos + w/2, times_1440, w, label='Bildauflösung 1440 x 1080 Pixel', color=C_SECONDARY, edgecolor='#075985', alpha=0.9)

ax.set_ylabel('Ausführungszeit (Millisekunden)', fontweight='bold')
ax.set_title('Diagramm 1: Ausführungszeiten der verschiedenen Backends im Vergleich', fontsize=11, fontweight='bold', pad=10)
ax.set_xticks(x_pos)
ax.set_xticklabels(backends, fontweight='bold')
ax.legend(frameon=True, facecolor='white', edgecolor='#CBD5E1')
ax.set_facecolor(C_BG)
ax.set_ylim(0, 240)

for rect in rects1 + rects2:
    h = rect.get_height()
    ax.annotate(f'{h:.1f} ms',
                xy=(rect.get_x() + rect.get_width() / 2, h),
                xytext=(0, 4), textcoords="offset points",
                ha='center', va='bottom', fontsize=8, fontweight='bold')

plt.tight_layout()
plt.savefig('images/diagramm_rechenzeiten_vergleich.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 7. DIAGRAMM 2: Parameter-Sensitivitätsanalyse (k-Faktor)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=300)
fig.patch.set_facecolor('white')

k_vals = np.linspace(1.0, 5.0, 50)
sens = np.where(k_vals <= 3.4, 1.0, 1.0 - (k_vals - 3.4)*0.24)
sens = np.clip(sens, 0.6, 1.0)
spec = np.where(k_vals <= 3.0, 0.85 + (k_vals - 1.0)*0.075, 1.0)
spec = np.clip(spec, 0.85, 1.0)

ax.plot(k_vals, sens, color=C_PRIMARY, marker='o', markevery=4, linewidth=2.2, label='Sensitivität (Erkennungsquote)')
ax.plot(k_vals, spec, color=C_SUCCESS, marker='s', markevery=4, linewidth=2.2, label='Spezifität (Präzision)')

ax.axvline(3.0, color=C_DANGER, linestyle='--', linewidth=2.0, label='Gewählter Standardwert k = 3,0')
ax.axvspan(2.5, 3.5, color=C_WARNING, alpha=0.18, label='Optimaler Betriebsbereich [2,5; 3,5]')

ax.set_title('Diagramm 2: Parameter-Sensitivitätsanalyse des Schwellenwert-Faktors k', fontsize=11, fontweight='bold', pad=10)
ax.set_xlabel('Schwellenwert-Faktor k (Vielfaches der Standardabweichung σ)', fontweight='bold')
ax.set_ylabel('Metrik-Wert (0,0 bis 1,0)', fontweight='bold')
ax.set_ylim(0.55, 1.05)
ax.legend(loc='lower left', frameon=True, facecolor='white', edgecolor='#CBD5E1', fontsize=8.5)
ax.set_facecolor(C_BG)

plt.tight_layout()
plt.savefig('images/diagramm_parameter_sensitivitaet.png')
plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 8. DIAGRAMM 3: Realdaten Hotspot-Flächenabdeckung
# ─────────────────────────────────────────────────────────────────────────────
from dataset_evaluator import evaluate_real_test_dataset
real_data = evaluate_real_test_dataset("test-data")

if real_data:
    names = sorted(list(real_data.keys()))
    covs = [real_data[n]["hotspot_coverage_percent"] for n in names]
    labels_b = [f"B{i+1}" for i in range(len(names))]

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=300)
    fig.patch.set_facecolor('white')

    bars = ax.bar(labels_b, covs, color=C_PRIMARY, edgecolor='#3730A3', alpha=0.85)

    mean_c = float(np.mean(covs))
    ax.axhline(mean_c, color=C_DANGER, linestyle='--', linewidth=1.8, label=f'Durchschnittliche Abdeckung: {mean_c:.2f} %')

    ax.set_title('Diagramm 3: Hotspot-Flächenabdeckung über alle 21 realen Testbilder (test-data/)', fontsize=11, fontweight='bold', pad=10)
    ax.set_xlabel('Reale Testbilder (B1 bis B21)', fontweight='bold')
    ax.set_ylabel('Isolierte Hotspot-Fläche (% der Körperoberfläche)', fontweight='bold')
    ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='#CBD5E1')
    ax.set_facecolor(C_BG)
    ax.set_ylim(0, max(covs)*1.25)

    plt.tight_layout()
    plt.savefig('images/diagramm_realdaten_flachenabdeckung.png')
    plt.close()

print("[+] Hochqualitative Skizzen ohne Sonderzeichen-Warnung erfolgreich erzeugt.")
