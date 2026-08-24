# Performance and Optimization Guide

This guide describes optimization techniques and architectural patterns used within the **IGNITE Medical Imaging Suite**.

---

## Multi-Tier Compute Hierarchy

IGNITE implements a three-tier execution hierarchy:

1. **PyTorch CUDA Backend (<10 ms):**
   Selected automatically when compatible NVIDIA hardware is detected. Executes vectorized tensor transformations directly on the GPU.

2. **Rust Native Core (~20–30 ms):**
   High-performance CPU path compiled with Link-Time Optimization (LTO) and Rayon multithreading. Uses zero-copy NumPy array views via PyO3.

3. **Python Fallback (~75–90 ms):**
   Standard CPU path using OpenCV and NumPy for cross-platform compatibility without compiling native binaries.

---

## Compiling for Maximum Performance

To compile the native Rust core with full release optimizations:

```bash
# Ensure Rust toolchain is installed
rustup default stable

# Build optimized Python extension wheel
maturin develop --release
```

Release compilation flags in `Cargo.toml`:
* `opt-level = 3`
* `lto = true`
* `codegen-units = 1`
* `panic = "abort"`
