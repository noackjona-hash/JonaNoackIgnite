# Performance and Optimization Guide (v5.0.0)

This guide describes optimization techniques, compilation workflows, and architectural patterns within the **IGNITE Medical Imaging Suite**.

---

## Multi-Tier Compute Hierarchy

IGNITE implements a modular compute hierarchy balancing hardware efficiency, clinical flexibility, and deployment simplicity:

1. **Go 1.27 Native Core + AVX2 SIMD (`core/ignite-core.exe`):**
   * High-performance native executable written in Go with Plan9 assembly kernels.
   * Eliminates external C/C++ compiler and runtime dependencies.
   * Executes 32-pixel parallel operations per cycle (`VPMINUB`, `VPMAXUB`, `VPSUBUSB`, `thresholdMaskAVX2`) and 8-wide Float32 FMA for Gaussian vesselness filters.
   * Latency: **1.4 ms** at $160 \times 120$ sensor resolution, **~169 ms** full diagnostic pipeline at $1440 \times 1080$.

2. **C# .NET 10 WPF Medical Workstation (`desktop/`):**
   * Hardware-accelerated presentation layer using Direct3D rendering for 0.0 ms CPU false-color palette mapping.
   * Synchronous dual-viewport zoom/pan, interactive curtain wipe slider, and 2.5D isometric relief topographer.
   * Communicates with the native core via zero-copy in-memory streams and structured JSON IPC.

3. **Embedded GopherLua Clinical Rule Engine (`rules/`):**
   * Decouples medical diagnostic logic from compiled code.
   * Clinicians can adjust threshold formulas (Armstrong $\Delta T \ge 2.2\,\text{K}$, edge gradient, halo contrast) in plain text scripts without recompiling.

4. **PyTorch CUDA & Python CLI (`cli.py`, `image_processing.py`):**
   * Secondary diagnostic and research tool for batch evaluation and headless pipelines.
   * Utilizes PyTorch CUDA tensor cores when NVIDIA hardware is available.

---

## Build & Compilation Instructions

### 1. Compiling the Go Native Core
Ensure Go 1.27+ is installed:
```bash
cd core
# Run automated SIMD and clinical test suite
go test -v ./pkg/...

# Build production binary with stripped debug symbols
go build -ldflags="-s -w" -o ignite-core.exe ./cmd/ignite-core
cd ..
```

### 2. Compiling the C# .NET 10 Desktop Suite
Ensure .NET 10 SDK is installed:
```bash
cd desktop
dotnet build -c Release Ignite.Desktop.csproj
dotnet run -c Release --no-build
cd ..
```

### 3. Building the Standalone Windows Installer
Ensure Inno Setup 6 is installed:
```powershell
.\installer\build_installer.ps1
```
Generates `dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe` with LZMA2/Ultra64 compression.

---

## Key Optimization Guidelines

1. **Keep Extreme Distal Boundaries Intact:**  
   Never apply aggressive morphological erosion ($\ge 5\%$) to raw anatomical masks. Always use micro-margins ($\le 0.5\%$, 1–2 px) combined with gradient-aware edge preservation ($G_{\text{edge}} \ge 3.0$) to prevent erasing thin digits (toes and fingers).

2. **Calibrate 3D Angular Emissivity Physics:**  
   Directional LWIR emissivity compensation must not exceed $k_\theta \le 1.2\,\text{K}$ (max $12$ raw units) to avoid creating artificial hyperthermic bulges on sloped tissue surfaces like the foot arch.

3. **Use Physiological Viability Floors:**  
   Avoid rigid whole-body median truncation ($I \ge \text{OrigMedian}$) in binarization stages. Use adaptive biological tissue floors ($\min(\max(\tilde{\mu} \cdot 0.55, 45), 80)$) to retain hypothermic extremities ($24–30\,^\circ\text{C}$).

4. **Sort by Clinical Severity, Not Absolute Pixel Value:**  
   Always rank findings by diagnostic risk score and focal elevation ($\text{Score} \cdot 100 + \Delta T_{\text{focal}}$) so that localized pathological infections are prioritized over naturally warm baseline tissue.
