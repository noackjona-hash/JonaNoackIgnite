## Summary of Changes
A concise summary of what this pull request introduces, fixes, or improves.

---

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Performance improvement (e.g., Rust core, Rayon multithreading, GPU kernel)
- [ ] Scientific validation / Benchmarking (dataset evaluation, metric calibration)
- [ ] GUI / UX improvement (Google Material 3 design, dialog enhancements)
- [ ] Documentation update
- [ ] Code cleanup and refactoring

---

## Testing & Validation Checklist
- [ ] `pytest tests/` passes locally without failures.
- [ ] Numerical parity validated across Python, Rust, and GPU backends (if applicable).
- [ ] No regression in Dice score or sensitivity on benchmark dataset (`dataset_evaluator.py`).
- [ ] Manual verification completed in the graphical user interface (`python main.py`).

---

## Benchmarks / Visual Evidence (if applicable)
*Include relevant before/after screenshots, runtime metrics, or benchmark output.*

---

## Privacy & Compliance
- [ ] Confirmed no unhashed patient identifiable information is persisted to disk or logs.
