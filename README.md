# IGNITE Medical Imaging Suite

**IGNITE** is the graphical desktop client of **ThermoAI Vision**, an advanced diagnostic platform for automated inflammation detection in thermal images. Developed as a research project for the German Youth Science Competition (**Jugend forscht 2026**), IGNITE provides clinical researchers and medical professionals with a responsive, high-contrast interface to execute advanced computer vision pipelines on thermal data.

---

## Key Features

* **Zero-Lag Instant Splash Screen:** Launches a lightweight Tkinter-based splash loader immediately upon execution. Heavy dependencies load asynchronously in the background.
* **Modern CustomTkinter Dashboard:** Styled with a dark-mode interface, leveraging custom cards, charts, and control panels based on Google Material 3 guidelines.
* **Intelligent Thermal Processing:** Integrates bilateral filtering, CLAHE, multi-scale morphological top-hat transforms, and gradient divergence analysis.
* **Radiometric Emissivity Calibration:** Applies Stefan-Boltzmann radiation models with human skin emissivity ($\epsilon = 0.98$) and reflected ambient temperature correction.
* **Quantitative Benchmarking & Clinical Dataset Evaluation:** Evaluates controlled synthetic noise scenarios (achieving 1.00 sensitivity/specificity under Gaussian noise $\sigma=2.5$ and 0.88-0.91 Dice metrics) and processes 21 clinical test images (`test-data/`), logging hotspot coverage statistics.
* **Aspect-Ratio Invariant Kernel Scaling:** Dynamically scales morphological kernels based on $\min(W, H)$ to ensure consistent detection performance across diverse camera resolutions.
* **Strict GDPR/HIPAA Compliance & EU-MDR Research Disclaimer:** Built with privacy by design. Pseudonymizes patient records via SHA-256 salted hashes (`ANON-<hash>`) and processes all data locally in-memory. *Note: Developed as a research prototype for Jugend forscht 2026; not an EU-MDR certified medical device.*

---

## Technical Architecture

IGNITE decouples analytical computations and UI threads across a hybrid multi-backend system:

```
[User Action] ──> [CustomTkinter Event Loop]
                         │
                         ├── (CUDA Acceleration)   ──> [PyTorch VRAM Kernels] (<10ms)
                         ├── (Native Multi-Thread) ──> [Rust Core / Rayon] (~30ms)
                         └── (CPU Fallback)       ──> [OpenCV / NumPy] (~80ms)
```

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

# Optional: Enable GPU acceleration (when NVIDIA CUDA is available)
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Optional: Compile native Rust core for maximum CPU performance
maturin develop --release
```

### 3. Run the application
```bash
python main.py
```

### 4. Run benchmarks and test suite
```bash
python dataset_evaluator.py    # Full benchmark suite (Rust vs Python vs GPU)
pytest tests/                  # Unit and numerical parity test suite
```

---

## Performance Optimization Matrix

| Deployment Target | Recommended Configuration |
| :--- | :--- |
| **Standard / Quick Demo** | Default configuration (GPU lazy-loaded, Python fallback) |
| **Medical Workstation (CPU)** | Compile native Rust core: `maturin develop --release` |
| **High-End GPU Workstation** | Install PyTorch CUDA: `pip install torch` (<10ms latency) |
| **Minimal Installation** | Standard Python requirements without Matplotlib |

The splash screen ensures a startup latency of less than 50ms across all execution environments.
