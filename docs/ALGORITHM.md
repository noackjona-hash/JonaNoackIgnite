# Architecture & Mathematics of the IGNITE Thermal Detection Algorithm (v5.0.0)

The hotspot detection algorithm in **IGNITE** extracts pathological inflammation foci (hyperthermia hotspots), maps vascular trees (veins), and measures perfusion asymmetries from medical thermographic imagery. It is implemented as a multi-stage deterministic image processing pipeline.

The complete implementation is available in the Go + AVX2 core at [`core/`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/core/) and exposed to the desktop interface at [`desktop/`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/desktop/).

---

## State of the Art & Methodological Comparison

Medical thermography regularly contends with artifacts including high-frequency sensor noise, global perfusion gradients, and environmental thermal reflections. The table below contrasts **IGNITE** with existing methodologies:

| Criterion | Manual Visual Inspection | Global Otsu Thresholding | Deep Learning (U-Net / SAM) | IGNITE v5.0.0 |
| :--- | :---: | :---: | :---: | :---: |
| **Determinism & Interpretability** | Subjective | High | Black-box | Deterministic (100%) |
| **Local Privacy (GDPR / HIPAA)** | Inherent | Inherent | Often requires cloud APIs | 100% In-Memory Local Processing + SQLite Audit |
| **Vascular & Vein Differentiation** | Moderate | None | Requires training data | Multiscale Frangi Vesselness Filter (Hessian) |
| **Bilateral Armstrong Symmetry** | Manual mental check | None | Rare | Automated mirror registration ($\Delta T \ge 2.2$ K) |
| **Dynamic Clinical Rules** | Subjective | Fixed | Black-box weights | Embedded Lua script engine (no recompile) |
| **Hardware Latency** | Manual | Poor | GPU required | **1.4 ms** @160x120 / **~169 ms** total pipeline @1440x1080 |

---

## Pipeline Stages

### 1. Dynamic Aspect-Ratio Invariant Kernel Scaling
To ensure scale invariance across diverse camera sensor resolutions (e.g., $160 \times 120$ up to $1440 \times 1080$ pixels), morphological structuring element dimensions scale proportionally to $\min(W, H)$:
* **Calculation:** `raw = (min(W, H) * tophat_factor)` (default: `0.05` for 5% of minimum dimension).
* **Clamping:** Kernels are clamped to a minimum radius of 1 pixel.

---

### 2. Adaptive Tissue Segmentation (Body-Mask & Chamfer Erosion)
Before computing regional statistical distributions, background room temperature must be separated from warm anatomical tissue:
1. **Otsu Thresholding & Contrast Fallback:** Calculates global Otsu thresholding with dynamic range fallback for low-contrast imagery.
2. **Euclidean Distance Transform:** Computes foreground distance fields using a 2-pass Chamfer distance transform.
3. **Proportional Boundary Erosion:** Retains pixels with boundary distance exceeding the configured margin factor (default: 5%), eliminating perimeter sensor noise and toe boundary artifacts.

---

### 3. Multi-Scale Morphological Top-Hat Transform (x86_64 AVX2 SIMD)
Isolates localized thermal elevations while eliminating global temperature gradients:
1. **Morphological Opening:** Computes mathematical erosion followed by dilation, isolating features smaller than kernel radius:
   $$\text{Opening}(I) = (I \ominus K) \oplus K$$
2. **AVX2 Hardware Acceleration (`core/pkg/morphology/avx2_amd64.s`):**
   * `VPMINUB`: 32 simultaneous 8-bit unsigned min operations per clock cycle (`minVectorAVX2`).
   * `VPMAXUB`: 32 simultaneous 8-bit unsigned max operations per clock cycle (`maxVectorAVX2`).
   * `VPSUBUSB`: 32 simultaneous saturating subtractions per clock cycle (`subVectorAVX2`):
     $$\text{TopHat}(I) = I - \text{Opening}(I)$$

---

### 4. Statistical Outlier Thresholding (Robust MAD Mode with AVX2 SIMD)
Determines thresholds for statistically significant hyperthermia:
* **Median Absolute Deviation (MAD Mode):** Robust non-parametric thresholding resistant to large hyperthermic clusters or cold toes (bimodal distributions):
   $$\text{MAD} = \text{median}(|X - \text{median}|)$$
   $$\text{Threshold} = \text{Median} + k \cdot 1.4826 \cdot \text{MAD}$$
* Implemented in $O(N)$ linear time using histogram accumulators over 256 intensity bins.
* **AVX2 Vectorized Threshold & Masking (`thresholdMaskAVX2`):**
  Uses `VPBROADCASTQ`, `VPMAXUB`, `VPCMPEQB`, and `VPAND` to simultaneously compare the Top-Hat difference against threshold, verify minimum tissue temperature, and apply the Chamfer body mask for 32 pixels in parallel.

---

### 5. Geometric Noise & Circularity Filtering
Removes single-pixel noise and false positives:
1. **Contour Extraction:** Detects 4-connected candidate regions via breadth-first search (BFS).
2. **Minimum Area Clamping:** Rejects regions smaller than $\text{min\_area\_factor} \times \text{tissue\_pixels}$.
3. **Isoperimetric Circularity:** Rejects elongated boundary noise:
   $$C = \frac{4 \pi \cdot \text{Area}}{\text{Perimeter}^2} \ge 0.08$$

---

### 6. Vascular Mapping via Multiscale Frangi Vesselness Filter (AVX2 FMA Accelerated)
Differentiates tubular veins from circular inflammatory foci using the 2D Hessian matrix:
$$\mathcal{H} = \begin{bmatrix} I_{xx} & I_{xy} \\ I_{xy} & I_{yy} \end{bmatrix}$$
Across multiple spatial scales $\sigma \in \{1.0, 2.0, 3.0\}$:
* **Blobness Measure:** $R_B = |\lambda_1| / |\lambda_2|$
* **Structureness / Contrast:** $S = \sqrt{\lambda_1^2 + \lambda_2^2}$
* **Vesselness Response:**
  $$V(\sigma) = \begin{cases} \exp\left(-\frac{R_B^2}{2\beta^2}\right) \cdot \left(1 - \exp\left(-\frac{S^2}{2c^2}\right)\right), & \text{falls } \lambda_2 < 0 \\ 0, & \text{sonst} \end{cases}$$
* **SIMD Gaussian Acceleration (`fmaVectorFloat32AVX2`):**
  Separable 1D Gaussian kernel convolutions are computed using 256-bit AVX2 FMA instructions (`VMULPS` and `VADDPS`), processing 8 floating point values per cycle for an ~8x acceleration over scalar implementations.

---

### 7. Longitudinal Perfusion Gradient ($dT/dy$)
Analyzes the thermal gradient along the anatomical extremity axis (proximal to distal, top to bottom):
* Computes mean temperature profile $T(y)$ and gradient:
  $$\nabla T(y) = \frac{T(y+1) - T(y-1)}{2}$$
* Detects localized vascular drop-offs ($\max(-\nabla T)$). Sharp distal drops ($> 4.5\,\text{K}$) indicate suspected peripheral arterial disease (pAVK) or microangiopathy.

---

### 8. Bilateral Symmetry Analysis (Armstrong $\Delta T \ge 2.2$ K, AVX2 SIMD)
Distinguishes genuine unilateral pathology from benign symmetrical warmth (e.g. from friction or tight socks):
* The contralateral limb (e.g. right foot) is mirrored horizontally: $I_{\text{right, mirrored}}(x, y) = I_{\text{right}}(W - 1 - x, y)$.
* Difference matrix computed via AVX2 `absDiffVectorAVX2`:
  $$\Delta T(x, y) = |I_{\text{left}}(x, y) - I_{\text{right, mirrored}}(x, y)|$$
* Zonal evaluation (Heel, Midfoot, Metatarsal heads, Toes). Asymmetries exceeding $\Delta T \ge 2.2$ K trigger critical pre-ulcerative inflammation alerts.

---

### 9. Embedded Lua Clinical Rule Engine
Permits clinicians and researchers to adapt threshold formulas and decision logic dynamically:
* Script: `rules/armstrong_criteria.lua`
* Receives hotspot features (`area`, `circularity`, `max_val`, `delta_t`) and tissue baseline (`median`, `mad`).
* Returns qualitative risk level (`CRITICAL`, `MODERATE`, `BENIGN`) and German clinical recommendations without requiring application recompilation.

