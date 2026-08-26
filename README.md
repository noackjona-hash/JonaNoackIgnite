# IGNITE Medical Imaging Suite

**IGNITE** is the graphical desktop client of **ThermoAI Vision**, an advanced diagnostic platform for automated inflammation detection in thermal images. Developed as a research project for the German Youth Science Competition (**Jugend forscht 2026**), IGNITE provides clinical researchers and medical professionals with a responsive, high-contrast interface to execute advanced computer vision pipelines on thermal data.

---

## Key Features

* **Zero-Lag Instant Splash Screen:** Launches a lightweight Tkinter-based splash loader immediately upon execution. Heavy dependencies load asynchronously in the background.
* **Modern CustomTkinter Dashboard:** Styled with a dark-mode interface, leveraging custom cards, charts, and control panels based on Google Material 3 guidelines.
* **Deterministic Thermal Processing:** A fully traceable five-stage pipeline — body-mask extraction (Otsu + morphological closing + distance transform), separable morphological top-hat, statistical outlier thresholding (Gaussian or robust MAD), and geometric component filtering. No machine-learning model and no black-box inference is involved.
* **Radiometric Emissivity Model:** Implements the Stefan-Boltzmann radiation model with human skin emissivity ($\epsilon = 0.98$) and reflected ambient temperature correction. *Note: this path requires radiometric input. The FLIR ONE JPEG exports used in this project contain only relative 8-bit intensities, so absolute temperatures — and the $\Delta T > 2.2$ K podiatric criterion — could not be evaluated on the sample data.*
* **Reproducible Validation Harness:** `scripts/run_validation.py` regenerates every figure reported in the write-up from a fixed seed — runtime benchmarks, ground-truth metrics with bootstrap confidence intervals, a tuning/test split, a filter ablation and backend parity. Results are written to `docs/validation/validation_report.json`.
* **Honest Measured Results:** Validated against **9 manually annotated thermal images** (Dice **0.325 ± 0.159**, precision **0.99**, sensitivity **0.21**), significantly ahead of an Otsu baseline (Dice 0.004; paired Wilcoxon $p = 0.0046$). With the threshold factor tuned on a held-out split, Dice rises to **0.513** on 5 unseen images. See *Known Limitations* below.
* **Aspect-Ratio Invariant Kernel Scaling:** Dynamically scales morphological kernels based on $\min(W, H)$ to ensure consistent detection performance across diverse camera resolutions.
* **Strict GDPR/HIPAA Compliance & EU-MDR Research Disclaimer:** Built with privacy by design. Pseudonymizes patient records via SHA-256 salted hashes (`ANON-<hash>`) and processes all data locally in-memory. *Note: Developed as a research prototype for Jugend forscht 2026; not an EU-MDR certified medical device.*

---

## Technical Architecture

IGNITE decouples analytical computations and UI threads across a hybrid multi-backend system:

```
[User Action] ──> [CustomTkinter Event Loop]
                         │
                         ├── (Native Multi-Thread) ──> [Rust Core / Rayon]
                         ├── (CPU)                 ──> [OpenCV / NumPy]
                         └── (Optional GPU)        ──> [PyTorch CUDA Kernels]
```

### Measured backend performance
x86_64, 4 cores, 60 runs after 10 warm-ups, min / median:

| Backend | 160x120 (native sensor) | 1440x1080 (camera JPEG) |
| :--- | :---: | :---: |
| **Rust core (rayon)** | **1.2 / 1.6 ms** | 86.4 / 104.3 ms |
| **Python + OpenCV** | – | 40.6 / 43.9 ms |
| **PyTorch (CUDA)** | not validated | not validated |

> **The Rust core is not the faster backend.** Once both paths were aligned to the same
> single-scale algorithm, OpenCV's SIMD-optimised C++ morphology measured ~2.4x faster.
> The Rust core is justified instead by having **no native third-party runtime dependency**
> (< 25 MB installer instead of > 200 MB), deterministic cross-platform behaviour, memory
> safety and low RAM use. The CUDA path could not be validated on the available hardware
> (GTX 1050, compute capability 6.1, below PyTorch's 7.5 minimum) and is therefore
> **unverified**.

The FLIR ONE Pro thermal sensor is only 160x120 px; the 1440x1080 JPEG it exports is an
upscaled render carrying no extra thermal information. Downscaling to the native sensor
resolution before analysis is by far the largest available speed-up.

---

## Tech Stack

* **Programming Languages:** Python 3.10+, Rust (via PyO3 / Maturin)
* **High-Performance Core:** Rust `ignite_core` (`rayon`, `ndarray`, `imageproc`)
* **User Interface:** `customtkinter`, `tkinter`
* **Image Processing:** OpenCV (`opencv-python`), Pillow (`PIL`), NumPy
* **Deep Learning (GPU Backend):** PyTorch CUDA
* **Packaging & Bundling:** PyInstaller, Inno Setup

---

## Getting Started

### Prerequisites
Python 3.10+ and a Rust toolchain (optional for native core compilation).

### 1. Clone the repository
```bash
git clone https://github.com/noackjona-hash/JonaNoackIgnite.git
cd JonaNoackIgnite
```

### 2. Install dependencies
```bash
# Baseline installation
pip install -r requirements.txt

# Optional: enable the GPU backend (requires compute capability >= 7.5)
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Optional: compile the native Rust core (removes the OpenCV runtime dependency)
maturin develop --release
```

### 3. Run the application
```bash
python main.py
```

### 4. Run benchmarks and test suite
```bash
python scripts/run_validation.py   # Reproduces every number reported in docs/ (fixed seed)
python dataset_evaluator.py        # Synthetic regression scenarios + real-image coverage
pytest tests/                      # Unit and backend-parity test suite (49 tests)
```

`scripts/run_validation.py` writes `ignite_steps_output/validation_report.json`; a copy of
the committed run lives in `docs/validation/validation_report.json`.

---

## Performance Optimization Matrix

| Deployment Target | Recommended Configuration |
| :--- | :--- |
| **Fastest analysis on CPU** | Default OpenCV path — measured fastest of the three backends |
| **Dependency-free deployment** | Compile the Rust core: `maturin develop --release` (no OpenCV runtime needed) |
| **Lowest latency overall** | Downscale to the native sensor resolution (160x120) before analysis — 1.6 ms |
| **GPU workstation** | `pip install torch` — **unverified**, no compatible GPU was available for testing |

---

## Known Limitations

This is a research prototype. The following constraints are essential context for the
reported numbers:

* **Not a medical device.** No EU-MDR certification. It cannot replace a clinical
  diagnosis and is intended only as an orientation aid under professional supervision.
* **Sample data is not clinical.** The 21 images in `test-data/` were recorded by the
  author using a FLIR ONE / FLIR ONE Pro, with consent, from family and acquaintances who
  are **not diagnosed patients**. Annotations mark thermally conspicuous regions, not
  confirmed pathology.
* **Small sample, single annotator.** Only 9 images have ground-truth masks, produced
  unblinded by a single medically untrained person (the author). No intra- or inter-rater
  agreement (e.g. Cohen's kappa) is available, so the reference is not a gold standard.
* **Systematic area underestimation.** At precision 0.99 / sensitivity 0.21 the pipeline
  reliably locates a hotspot's core but not its extent — unsuitable for wound-area
  measurement.
* **No absolute temperatures.** JPEG exports carry only relative intensities from a
  per-image dynamic palette.
* **Backends are not bit-identical.** After alignment, Rust vs. Python mask IoU averages
  **0.78** (not 1.0). Exact equality is unattainable by design: the Rust core uses
  separable Lemire morphology with a rectangular structuring element ($O(K)$ instead of
  $O(K^2)$) and a Chamfer distance approximation, whereas OpenCV uses an elliptical kernel
  and different border handling. Tests assert a documented IoU floor instead.
* **Dataset-specific geometric filters.** The anatomical cutoff at 65 % image height and
  the border filter discard 0.0 % of annotated pixels on this dataset, but rely on a
  constant capture geometry; a heel lesion in the lower third would be suppressed.

Full analysis and discussion: [`docs/SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.md`](docs/SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.md)
and [`docs/ALGORITHM.md`](docs/ALGORITHM.md).
