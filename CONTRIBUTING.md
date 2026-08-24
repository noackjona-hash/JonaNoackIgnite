# Contributing to IGNITE Medical Imaging Suite

Thank you for your interest in contributing to **IGNITE**! This project was developed as a scientific research prototype for the German Youth Science Competition (**Jugend forscht 2026**).

We welcome contributions including bug reports, algorithmic improvements, documentation updates, and performance optimizations.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Contribute](#how-to-contribute)
   - [Reporting Bugs](#reporting-bugs)
   - [Requesting Features](#requesting-features)
   - [Submitting Pull Requests](#submitting-pull-requests)
3. [Development Setup](#development-setup)
4. [Development Guidelines](#development-guidelines)
   - [Python Code Standards](#python-code-standards)
   - [Rust Core (ignite_core)](#rust-core-ignite_core)
   - [User Interface & Design](#user-interface--design)
5. [Running Tests and Benchmarks](#running-tests-and-benchmarks)
6. [Pull Request Workflow](#pull-request-workflow)

---

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please maintain a professional, respectful, and constructive tone in all interactions.

---

## How to Contribute

### Reporting Bugs
If you encounter a bug or unexpected behavior, please submit an issue using our [Bug Report Form](.github/ISSUE_TEMPLATE/bug_report.yml):
* Provide a clear and concise description of the issue.
* List reproducible, step-by-step instructions.
* Specify your operating system, Python version, compute backend, and hardware details.
* Include relevant log outputs or stack traces.

### Requesting Features
For new features, diagnostic tools, or mathematical algorithms, please use our [Feature Request Form](.github/ISSUE_TEMPLATE/feature_request.yml):
* Explain the rationale and clinical/scientific utility of the proposed feature.
* Describe the desired implementation and any alternative solutions considered.

---

## Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/noackjona-hash/JonaNoackIgnite.git
cd JonaNoackIgnite
```

### 2. Configure Virtual Environment & Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Linux/macOS
# or venv\Scripts\activate on Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Compile Native Rust Core (Recommended)
```bash
maturin develop --release
```

### 4. Run the Application
```bash
python main.py
```

---

## Development Guidelines

### Python Code Standards
* Follow PEP 8 style conventions.
* Provide explicit type annotations (`from typing import Optional, Any, ...`) across all modules.
* Maintain privacy-by-design principles: never write unhashed patient identifiable information to disk or logs. Always use `pseudonymize_patient()`.

### Rust Core (`src/lib.rs`)
* Enforce safe error handling: never use `unwrap()` or `expect()`. Propagate errors using `Result<T, String>` or `PyResult<T>`.
* Utilize zero-copy memory patterns with `PyReadonlyArray2` and `PyArray2`.
* Parallelize CPU-intensive loops along image rows using `rayon`.

### User Interface & Design
* Use design tokens and color constants defined in `gui/theme.py`.
* Strictly decouple UI view components (`gui/views/`, `gui/components/`) from core mathematical and export services (`image_processing.py`, `gui/services/`).

---

## Running Tests and Benchmarks

Ensure all automated tests pass before opening a pull request:

```bash
# Run unit and UI regression test suite
pytest tests/

# Run complete scientific benchmark and numerical parity suite
python dataset_evaluator.py
```

---

## Pull Request Workflow

1. Create a descriptive feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes and add corresponding test coverage under `tests/`.
3. Verify that `pytest tests/` completes with all tests passing.
4. Open a pull request following our [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
