# Architecture of the IGNITE Thermal Detection Algorithm

The hotspot detection algorithm in **IGNITE** extracts pathological inflammation foci (hyperthermia hotspots) from medical thermographic imagery. It is implemented as a multi-stage deterministic image processing pipeline.

The complete implementation is available in the native Rust core at [`src/lib.rs`](../src/lib.rs) and exposed via Python bindings in [`image_processing.py`](../image_processing.py).

---

## State of the Art & Methodological Comparison

Medical thermography regularly contends with artifacts including high-frequency sensor noise, global perfusion gradients, and environmental thermal reflections. The table below contrasts **IGNITE** with existing methodologies:

| Criterion | Manual Visual Inspection | Global Otsu Thresholding | Deep Learning (U-Net / SAM) | IGNITE (ThermoAI) |
| :--- | :---: | :---: | :---: | :---: |
| **Determinism & Interpretability** | Subjective | High | Black-box | Deterministic (100%) |
| **Local Privacy (GDPR / HIPAA)** | Inherent | Inherent | Often requires cloud APIs | 100% In-Memory Local Processing |
| **Local Hotspot Isolation** | Moderate | Poor | Good | Good (Top-Hat + geometric filtering) |
| **Consumer Hardware Latency** | Manual | see note | GPU required | 1.6 ms @160x120, 104 ms @1440x1080 (Rust CPU, measured) |
| **Empirical Sensitivity / Specificity** | N/A | 0.005 / 0.982 (measured) | not evaluated here | 0.206 / 1.000 (measured) |
| **Bimodal Noise Robustness (MAD)** | No | No | Learned | Robust MAD & Gaussian options |

---

## Pipeline Stages

### 1. Dynamic Aspect-Ratio Invariant Kernel Scaling
To ensure scale invariance across diverse camera sensor resolutions (e.g., $160 \times 120$ up to $1440 \times 1080$ pixels), morphological structuring element dimensions scale proportionally to $\min(W, H)$:
* **Calculation:** `raw = (min(W, H) * tophat_factor)` (default: `0.05` for 5% of minimum dimension).
* **Odd-Dimension Enforcement:** To guarantee a distinct center anchor for morphological kernels, bitwise odd enforcement is applied: `odd = (raw | 1)`.
* **Lower Bound:** Kernels are clamped to a minimum size of $3 \times 3$ pixels.

---

### 2. Adaptive Tissue Segmentation (Body-Mask)
Before computing regional statistical distributions, background noise must be separated from warm anatomical tissue:
1. **Multi-Otsu Thresholding & Contrast Fallback:** Calculates global Otsu thresholding with dynamic range fallback for low-contrast imagery.
2. **Euclidean Distance Transform:** Computes foreground distance fields using a two-pass Chamfer distance transform.
3. **Proportional Erosion:** Retains pixels with boundary distance exceeding the configured margin factor (default: 5%), eliminating perimeter sensor noise and toe boundary artifacts.

---

### 3. Multi-Scale Morphological Top-Hat Transform
Isolates localized thermal elevations while mitigating global temperature gradients:
1. **Morphological Opening:** Computes mathematical erosion followed by dilation, isolating features smaller than kernel radius.
2. **Top-Hat Subtraction:** Subtracts background morphology from the input thermal matrix:
   $$\text{TopHat}(I) = I - \text{Opening}(I)$$
3. **Separable 1D Deque Optimization:** Decomposes 2D operations into sequential 1D horizontal and vertical passes, reducing computational complexity from $O(K^2)$ to $O(K)$ per pixel (Lemire monotonic queue algorithm).
4. **Tissue Masking:** Applies logical AND masking with the segmented body mask.

---

### 4. Statistical Outlier Thresholding
Determines thresholds for statistically significant hyperthermia:
* **Gaussian Mode ($\mu + k \cdot \sigma$):** Computes mean $\mu$ and standard deviation $\sigma$ exclusively across masked tissue pixels.
* **Median Absolute Deviation (MAD Mode):** Robust non-parametric thresholding resistant to large hyperthermic clusters:
   $$\text{Threshold} = \text{Median} + k \cdot 1.4826 \cdot \text{MAD}$$

---

### 5. Geometric Noise & Circularity Filtering
Removes single-pixel artifacts and false positives:
1. **Contour Extraction:** Detects 4-connected candidate regions.
2. **Minimum Area Clamping:** Rejects regions smaller than $\text{min\_area\_factor} \times \text{body\_pixels}$.
3. **Isoperimetric Circularity:** Rejects elongated boundary noise:
   $$C = \frac{4 \pi \cdot \text{Area}}{\text{Perimeter}^2} \ge 0.08$$

---

## Computational Complexity & Performance

| Stage | Theoretical Complexity | Rust CPU (Rayon), 1440x1080 |
| :--- | :--- | :--- |
| **Body Mask** (Otsu + closing + distance transform) | $O(H \cdot W)$ | 39.0 ms |
| **Separable Top-Hat** | $O(H \cdot W)$ | 26.8 ms |
| **Outlier Threshold** | $O(H \cdot W)$ | 2.5 ms |
| **Geometric Filter** | $O(N)$ | 5.7 ms |
| **Total Pipeline** | $O(H \cdot W)$ | **86.4 ms** (min) / 104.3 ms (median) |

Measured with `scripts/run_validation.py` on x86_64, 4 cores, 60 runs after 10 warm-up
runs. Per-stage numbers are minima obtained with `IGNITE_DEBUG=1`.

At the native resolution of the FLIR ONE Pro thermal sensor (160x120) the full pipeline
runs in **1.6 ms** (median). The 1440x1080 JPEG the camera exports is an upscaled render
and carries no additional thermal information.

> **Note on OpenCV comparison:** once both backends were aligned to the same single-scale
> algorithm, the OpenCV/Python path measured ~2.4x *faster* than this Rust core
> (43.9 ms vs 104.3 ms median @1440x1080). The Rust core is not justified by raw speed but
> by having no native third-party runtime dependency (< 25 MB installer), deterministic
> cross-platform behaviour and low memory use. The CUDA path could not be validated on the
> available hardware (GTX 1050, compute capability 6.1) and is therefore not benchmarked.
