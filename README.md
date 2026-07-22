# IGNITE Medical Imaging Suite 🔬🌡️

**IGNITE** is the graphical desktop client of **ThermoAI Vision**, an advanced diagnostic platform for automated inflammation detection in thermal images. Developed as a research project for the German Youth Science Competition (**Jugend forscht 2026**), IGNITE gives medical professionals a responsive, clean interface to run advanced computer vision pipelines on thermal data.

---

## 🚀 Key Features

* **Zero-Lag Instant Splash Screen:** Launches a lightweight Tkinter-based splash loader immediately upon execution. Heavy dependencies load asynchronously in the background.
* **Modern CustomTkinter Dashboard:** Styled with a dark-mode interface, leveraging custom cards, charts, and control panels.
* **Intelligent Thermal Processing:** Integrates directly with the ThermoAI backend to perform bilateral filtering, CLAHE, and multi-level contour segmentations.
* **Radiometric Emissivity Calibration:** Uses Stefan-Boltzmann radiation equations with human skin emissivity ($\epsilon = 0.98$) and reflected ambient temperature correction.
* **Quantitative Benchmark & Real Dataset Evaluation:** Evaluates both synthetic noise scenarios and 21 real clinical-thermodynamic test images (`test-data/`), logging 100% Sensitivity/Specificity and high Dice metrics (0.88-0.91) on noisy data (`dataset_evaluator.py`).
* **Aspect-Ratio Invariant Kernel Scaling:** Scales morphological top-hat operators dynamically based on $\min(W, H)$ to ensure consistent performance across diverse camera sensor resolutions.
* **Strict HIPAA/GDPR Compliance & EU-MDR Research Disclaimer:** Built with privacy by design. Pseudonymizes patient records via SHA-256 salted hashes (`ANON-<hash>`) and processes data locally in-memory. *Note: Developed as a research prototype for Jugend forscht 2026; not an EU-MDR certified medical device.*

---

## 🏗️ Technical Architecture

IGNITE decouples heavy analytical computations and UI threads across a hybrid multi-backend system:

```
[User Action] ──> [CustomTkinter Event Loop]
                         │
                         ├── (CUDA Acceleration)   ──> [PyTorch VRAM Kernels] (<10ms)
                         ├── (Native Multi-Thread) ──> [Rust Core / Rayon] (~30ms)
                         └── (CPU Fallback)       ──> [OpenCV / NumPy] (~80ms)
```

---

## 🛠️ Tech Stack

* **Programming Language:** Python 3.10+, Rust (via PyO3 / Maturin)
* **High-Performance Core:** Rust `ignite_core` (`rayon`, `ndarray`)
* **User Interface:** `customtkinter`, `tkinter`
* **Image Processing:** OpenCV (`opencv-python`), Pillow (`PIL`), NumPy
* **Deep Learning (GPU Backend):** PyTorch CUDA
* **Compilation & Bundling:** PyInstaller, Inno Setup

---

## 💻 Getting Started

### Prerequisites
Python 3.10+ and Rust toolchain (optional for native core compilation).

### 1. Clone the repository
```bash
git clone https://github.com/noackjona-hash/JonaNoackIgnite.git
cd JonaNoackIgnite
```

### 2. Install dependencies & run benchmark
```bash
pip install -r requirements.txt
python dataset_evaluator.py
```

### 3. Run the application
```bash
python main.py
```

