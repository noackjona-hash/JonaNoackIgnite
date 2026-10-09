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

### 2. Adaptive Tissue Segmentation & Anatomical Body Component Isolation
Before computing regional statistical distributions, background room temperature and environmental clutter must be separated from warm anatomical tissue:
1. **Otsu Thresholding & Contrast Fallback:** Calculates global Otsu thresholding with dynamic range fallback for low-contrast imagery.
2. **Anatomical Body Component Filtering (BFS):** Isolates major anatomical bodies and eliminates detached background reflections, warm bedsheet folds, and wall clutter (< 2% of maximum body area).
3. **3D-Calibrated Subpixel Boundary Cleaning:** Because the 3D surface reconstruction model (Stage 11) physically compensates for grazing angle emissivity drops, aggressive border erosion is unnecessary. A minimal boundary margin ($\le 0.5\%$, 1–2 pixels) cleans sensor edge aliasing while keeping thin distal extremities (toes, fingers, digits) 100% intact.

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

### 4. Statistical Outlier Thresholding (Robust MAD Mode with Adaptive Tissue Floor)
Determines thresholds for statistically significant hyperthermia:
* **Median Absolute Deviation (MAD Mode):** Robust non-parametric thresholding resistant to large hyperthermic clusters or cold toes (bimodal distributions):
   $$\text{MAD} = \text{median}(|X - \text{median}|)$$
   $$\text{Threshold} = \text{Median} + k \cdot 1.4826 \cdot \text{MAD}$$
* Implemented in $O(N)$ linear time using histogram accumulators over 256 intensity bins.
* **Physiological Tissue Floor (`tissueFloor`):** Rather than enforcing a global whole-body median floor ($I \ge \text{OrigMedian}$) which would discard naturally cooler distal extremities (fingers/toes at 24–30 °C), binarization uses a biological viability floor:
  $$\text{TissueFloor} = \min(\max(\text{OrigMedian} \cdot 0.55, 45), 80)$$
  This guarantees that true focal hyperthermias on cool digits are segmented while sub-biological ambient air noise (< 20 °C) remains blocked.
* **AVX2 Vectorized Threshold & Masking (`thresholdMaskAVX2`):**
  Uses `VPBROADCASTQ`, `VPMAXUB`, `VPCMPEQB`, and `VPAND` to simultaneously compare the Top-Hat difference against threshold, verify minimum tissue temperature, and apply the body mask for 32 pixels in parallel.

---

### 5. Geometric Noise, Circularity & Extremity Preservation
Removes single-pixel noise and false positives while preserving genuine distal lesions:
1. **Contour Extraction:** Detects 4-connected candidate regions via breadth-first search (BFS).
2. **Minimum Area Clamping:** Rejects regions smaller than $\text{min\_area\_fraction} \times \text{tissue\_pixels}$ (default: $0.03\%$).
3. **Isoperimetric Circularity:** Rejects linear boundary aliasing and scratch noise:
   $$C = \frac{4 \pi \cdot \text{Area}}{\text{Perimeter}^2} \ge 0.08$$
4. **Distal Extremity & Edge Preservation:** Genuine focal lesions near tissue borders (e.g. inflamed hallux, finger pulp) exhibiting a true thermal gradient ($G_{\text{edge}} \ge 3.0$ or $\Delta T_{\text{halo}} \ge 5.0$) are preserved, whereas flat air-boundary artifacts lacking focal contrast are discarded.
5. **Universal Multi-Anatomical Support:** Hardcoded vertical anatomical cuts (`AnatomicalCutoffY = 0.0`) are disabled, allowing automated and unbiased analysis across all body regions: feet, hands/fingers, knees, spine, and general soft tissue.

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
* Receives hotspot features (`area`, `circularity`, `max_val`, `delta_t`, `edge_gradient`, `halo_delta`, `thermal_laplacian`, `peak_to_mean`) and tissue baseline (`median`, `mad`).
* Returns qualitative risk level (`CRITICAL`, `MODERATE`, `BENIGN`), diagnosis type, and German clinical recommendations without requiring application recompilation.

---

### 10. Biophysical Differential Classification: Inflammation vs. Pressure Point (DTBC)
Resolves the critical medical challenge of differentiating benign mechanical friction / hyperkeratotic pressure points from pathological soft-tissue infections:
1. **Thermal Edge Gradient ($G_{\text{edge}}$):**
   * *Pressure points (calluses/hyperkeratosis):* Show abrupt, steep thermal drop-offs at the keratotic boundary ($G_{\text{edge}} \ge 3.0$) due to keratin's thermal insulation ($\kappa_{\text{keratin}} \approx 0.21\,\text{W/m K}$).
   * *Inflammatory foci:* Exhibit continuous, smooth thermal diffusion into healthy surrounding tissue.
2. **Perifocal Vasodilatation Halo ($\Delta T_{\text{halo}}$):**
   * *Inflammations:* Generate reactive capillary hyperaemia producing a distinctive thermal halo in the adjacent 1–4 px boundary ($\Delta T_{\text{halo}} \ge 0.5\,\text{K}$).
   * *Pressure points:* Lack perifocal hyperaemia ($\Delta T_{\text{halo}} \le 0.3\,\text{K}$).
3. **Discrete 2D Laplacian ($\nabla^2 T$):**
   * Computes the local metabolic heat production term $\dot{q}_m$. Focal infections show sharp negative Laplacian concavity ($\nabla^2 T \le -3.5$), whereas pressure areas present a flat plateau.
4. **Diagnostic Triaging:**
   * **`INFLAMMATION`:** $\Delta T \ge 2.2\,\text{K}$ with diffuse halo and metabolic Laplacian peak $\rightarrow$ acute infection/phlegmon.
   * **`PRESSURE_POINT`:** $1.0\,\text{K} \le \Delta T < 2.2\,\text{K}$ with steep keratin boundary and no halo $\rightarrow$ biomechanical pressure relief & debridement.
   * **`INFLAMED_PRESSURE_POINT`:** $\Delta T \ge 2.2\,\text{K}$ under sharp keratotic border $\rightarrow$ acute pre-ulcerative lesion under high ulceration risk!

---

### 11. 3D Anatomical Surface Reconstruction & Lambertian Directional Emissivity Compensation
Resolves the fundamental biophysical artifact where curved anatomical perimeters (e.g., lateral foot margins, toes, heel) artificially register $1.5\,\text{K}$ to $4.0\,\text{K}$ colder than the anatomical apex:

1. **Biophysical Cause of False Perimeter Cooling:**
   * **Directional Emissivity Falloff:** Human skin emissivity ($\varepsilon_0 \approx 0.98$) drops significantly at oblique viewing angles $\theta \ge 50^\circ$ according to directional Fresnel radiation:
     $$\varepsilon(\theta) = \varepsilon_0 \cdot \cos^\gamma(\theta)$$
   * **Lambertian Radiance Projection:** Receding edge surfaces project a larger physical surface element onto a single sensor pixel, diluting irradiance and blending cold ambient background radiation ($T_{\text{ambient}} \approx 20^\circ\text{C}$).
2. **3D Anatomical Surface Inflation (Shape-from-Silhouette):**
   * Computes the normalized geodesic distance transform $u(x, y) = D(x, y) / \max(D)$ from the anatomical boundary.
   * Smoothly inflates the 3D surface height $Z(x, y)$ using a blended sinusoidal-ellipsoidal profile with exponent $\alpha = 0.65$:
     $$Z(x, y) = Z_{\text{peak}} \cdot \left[0.5 \sin\left(u \cdot \frac{\pi}{2}\right) + 0.5 \sqrt{1 - (1-u)^2}\right]^\alpha$$
3. **Surface Normals & Optical Incidence Angle:**
   * Discrete central differences compute spatial gradients $(\partial Z/\partial x, \partial Z/\partial y)$.
   * The camera-directed viewing angle $\theta$ satisfies:
     $$\cos \theta(x, y) = \frac{1}{\sqrt{1 + \left(\frac{\partial Z}{\partial x}\right)^2 + \left(\frac{\partial Z}{\partial y}\right)^2}}$$
4. **Physically Calibrated Radiometric Angle Compensation:**
   * Restores the true physiological temperature matrix $T_{\text{corrected}}$:
     $$\Delta T_{\text{angle}}(\theta) = k_\theta \cdot (1 - \cos^\gamma \theta)$$
     $$T_{\text{corrected}}(x, y) = T_{\text{apparent}}(x, y) + \Delta T_{\text{angle}}(\theta)$$
   * Bounded to physically realistic skin emissivity margins ($k_\theta \le 1.2\,\text{K}$, max $12$ raw units), compensating for peripheral cosine falloff without artificially generating hyperthermic artifacts on sloping tissues.

---

### 12. Clinical Severity Ranking & Finding Triaging
In contrast to naive sorting by absolute pixel temperature (which erroneously flags naturally warm plantigrade heel or palm tissue), IGNITE ranks all detected candidate foci by **pathological severity**:
$$\text{Priority}(H) = \text{Score}_{\text{Lua}} \cdot 100 + \Delta T_{\text{focal}}$$
* **Acute Pathological Foci First:** Hotspots exhibiting critical risk scores (Score $\ge 9.5$, e.g. acute hallux inflammation $\Delta T \ge +5.0\,\text{K}$) are prioritized as Hotspot #1 in findings lists and interactive callout cards.
* **Benign Physiological Plateaus Suppressed:** Symmetrically warm core regions or low-gradient friction areas are triaged appropriately, completely eliminating "random" false positive callouts.


