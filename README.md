# IGNITE Medical Imaging Suite 🔬🌡️

**IGNITE** is the graphical desktop client of **ThermoAI Vision**, an advanced diagnostic platform for automated inflammation detection in thermal images. Developed as a research project for the German Youth Science Competition (**Jugend forscht 2026**), IGNITE gives medical professionals a responsive, clean interface to run advanced computer vision pipelines on thermal data.

---

## 🚀 Key Features

* **Zero-Lag Instant Splash Screen:** Launches a lightweight Tkinter-based splash loader immediately upon execution. Heavy dependencies (such as OpenCV, PyTorch, and CustomTkinter) load in the background without freezing or delaying the initial program startup window.
* **Modern CustomTkinter Dashboard:** Styled with a premium Dark Mode interface, leveraging custom cards, charts, and control panels.
* **Intelligent Thermal Processing:** Integrates directly with the ThermoAI backend to perform bilateral filtering, CLAHE (Contrast Limited Adaptive Histogram Equalization), and multi-level contour segmentations.
* **Anatomical Foot Mapping:** Performs automatic keypoint tracking on foot images to isolate individual toes and heel areas, calculating thermal discrepancies between symmetrical limbs.
* **Strict HIPAA/GDPR Compliance:** Built with privacy by design. Images are processed locally or sent over encrypted TLS streams to a local FastAPI backend. Calculations occur in-memory, and raw thermal files are securely purged immediately after processing.

---

## 🏗️ Technical Architecture

IGNITE is designed to decouple heavy analytical computations and UI threads:

```
[User Action] ──> [CustomTkinter Event Loop]
                         │
                         ├── (Heavy Imports / AI Load) ──> [Background Worker Thread]
                         │
                         └── (Local Analysis API)      ──> [OpenCV / NumPy / PyTorch Kernels]
```

* **Module Preloading:** Python's startup time can be sluggish when importing large ML frameworks. By launching the lightweight GUI thread first and loading imports asynchronously in a background thread, IGNITE delivers a native app feel.
* **Landmark Recognition:** Uses localized thresholding algorithms and shape factor analyses to locate feet outlines and determine the primary region of interest (ROI).

---

## 🛠️ Tech Stack

* **Programming Language:** Python 3.10+
* **User Interface:** `customtkinter` (advanced Tkinter extensions), `tkinter`
* **Image Processing:** OpenCV (`opencv-python`), Pillow (`PIL`), NumPy
* **Deep Learning (Backend):** PyTorch
* **Threading & OS:** Python `threading` library, `os`, `sys`
* **Compilation & Bundling:** `pyinstaller`

---

## 💻 Getting Started

### Prerequisites
Make sure Python 3.10 or higher is installed.

### 1. Clone the repository
```bash
git clone https://github.com/noackjona-hash/JonaNoackIgnite.git
cd JonaNoackIgnite
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
```bash
python main.py
```
