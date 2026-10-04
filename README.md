<p align="center">
  <img src="logo.png" alt="Selective Logo" width="500"/>
</p>

# Selective

> **Safety-Analyzed, Demand-Driven Package Loading for Python**  
> *Tagline: Load only what you need, prove observable equivalence, and explain every decision.*

Selective is an ahead-of-time (AOT) package safety analyzer and runtime demand loader for Python (CPython 3.10+). It solves Python's eager import bottleneck in large third-party packages (**PyTorch**, **pandas**, **SciPy**, **NumPy**, **TensorFlow**, **Transformers**), where `import pkg` initializes far more submodules, native libraries, and decorators than a program ever uses.

---

## 🚀 Key Highlights & Empirical Performance

Selective eliminates up to **97% of startup import overhead** without modifying installed packages on disk or executing code during analysis.

### Startup Acceleration (Measured Benchmarks)

| Framework | Workload | Baseline Eager Import | Selective Optimized | Speedup (%) | Import Time Saved |
|---|---|---|---|---|---|
| **PyTorch** | A (tensor initialization) | 1.550 s | **0.078 s** | **95.0%** | **1,472 ms** |
| **PyTorch** | C (Adam optimizer) | 2.327 s | **0.067 s** | **97.1%** | **2,260 ms** |
| **SciPy** | B (optimize minimize) | 0.691 s | **0.066 s** | **90.4%** | **625 ms** |
| **SciPy** | C (stats norm pdf) | 1.068 s | **0.068 s** | **93.6%** | **1,000 ms** |
| **pandas** | A (tiny DataFrame) | 0.470 s | **0.082 s** | **82.5%** | **387 ms** |
| **pandas** | B (Groupby mean) | 0.450 s | **0.117 s** | **74.1%** | **333 ms** |
| **NumPy** | C (linalg svd) | 0.136 s | **0.064 s** | **52.5%** | **72 ms** |

- **Finder Microbenchmark Overhead**: `< 0.150 microseconds` per `find_spec` lookup on unmanaged imports.
- **False-Optimization Rate**: **0.0 / 1000** (Zero OEC verification diffs).

---

## 🛠️ Installation & Quick Start

```bash
# Clone the repository and install editable
git clone https://github.com/selective/selective.git
cd Selective
pip install -e .
```

### 1. Scan an Entire Project Directory
Discover and analyze all third-party dependencies used across your project's `.py` files automatically:

```bash
selective scan /path/to/my_project --project
```

```text
[Selective] Scanning project directory at '/path/to/my_project'...
[Selective] Discovered 4 third-party package dependencies: numpy, pandas, scipy, torch
  Scanning package 'numpy'...
  Scanning package 'pandas'...
  Scanning package 'scipy'...
  Scanning package 'torch'...
[Selective] Project scan complete. Manifest written to: .selective/project_manifest.json
```

### 2. Run Application with Demand Loading
Run your script with transparent demand loading enabled:

```bash
selective run app.py
```

### 3. Inspect Decisions
Understand why any module or edge was classified as eager or lazy:

```bash
selective explain torch.nn
```

### 4. Verify Equivalence Contract
Run differential verification to ensure your optimized app behaves identically to standard CPython:

```bash
selective verify app.py
```

---

## 💡 How Selective Works: The 4 Pillars

```text
INSTALL / DISCOVER
      │
      ▼
AOT Safety Analyzer (No code execution) ──► Static & Safety Graphs ──► Load Plans
      │
      ▼
Differential Verification (OEC Harness L1-L5, Test Suites, Fuzzing)
      │
      ▼
Runtime Execution: Eager Skeleton + Demand-Driven Lazy Proxies
      │
      ├─► Touched: Resolve on demand (Thread-safe late load)
      ├─► Graph Violation: Fail open (Taint package, eager fallback, hint persistence)
      └─► Untouched: Cost is NEVER paid
```

### 1. Ahead-of-Time (AOT) Safety Analyzer
Scans package ASTs and shared libraries (`pyelftools`) statically **without importing or executing package code**:
- **Static Elimination**: Removes `if TYPE_CHECKING:` blocks and constant platform/version branches.
- **Side-Effect Detector**: Flags module-scope registration calls (`register_*`), system hooks (`atexit`, `signal`, `threading`), environment writes (`os.environ`), and audit hooks.
- **Native Binary Scanner**: Inspects ELF `DT_NEEDED`, `RPATH`, and `PyInit_*` symbols to preserve native extension load ordering (`NATIVE_REQUIRED`).
- **Safety Classification**: Categorizes edges into 6 evidence tiers (`SAFE_LAZY`, `CONDITIONALLY_LAZY`, `EAGER_REQUIRED`, `NATIVE_REQUIRED`, `SECURITY_EAGER`, `UNKNOWN`).

### 2. Source-Transform Loader
Rewrites package module bodies dynamically during import:
- **Strategy B (CPython 3.10 – 3.14)**: Rewrites module-scope imports to lazy descriptors (`LazyModuleProxy`) and installs PEP 562 `__getattr__` descriptors while preserving line numbers (`ast.copy_location`) and `inspect` / `linecache` compatibility.
- **Strategy A (CPython 3.15+)**: Prepends generated `__lazy_modules__ = [...]` lists to apply CPython's native explicit lazy import mechanism (PEP 810).
- **Isolated Bytecode Cache**: Caches transformed bytecode in `.selective/cache/` keyed by `sha256(source) + graph_id + transform_version + MAGIC_NUMBER`.

### 3. Observable Equivalence Contract (OEC) Harness
Enforces semantic equivalence across 5 strict levels via `selective verify`:
- **L1 Namespace**: `dir()` and `__all__` member consistency after resolution.
- **L2 Registries**: Dispatch tables (`torch.ops`), pandas accessors, and entry-point registries.
- **L3 Behavior**: Execution output, warnings, and return values.
- **L4 Process State**: Environment variables, recursion limits, RNG state, signal/atexit handlers.
- **L5 Error Timing**: `ImportError` exceptions occur exactly where expected.

### 4. Miss Path & Degradation Ladder
- **Thread-Safe Resolution**: Per-module reentrant locks (`threading.RLock`) with acyclic ordering rules to prevent deadlocks.
- **Fail Open**: If an unexpected attribute is missing or a graph violation occurs, Selective taints the package for the current process, immediately falling back to standard eager imports for all remaining stubs.

---

## 📖 CLI Command Reference

| Command | Usage | Description |
|---|---|---|
| `scan` | `selective scan [target] [--project] [--bake DIR]` | Scans a single package or an entire project directory (`--project`) |
| `explain` | `selective explain <module> [--unsafe]` | Explains why an import edge was classified lazy, eager, or unsafe |
| `verify` | `selective verify <script.py>` | Runs differential subprocess verification against OEC contract |
| `bisect` | `selective bisect <script.py>` | Bisects lazy edges to isolate minimal edge causing a diff |
| `doctor` | `selective doctor` | Displays environment diagnostics, cache writeability, and hook health |
| `install-hook` | `selective install-hook` | Installs `.pth` / `sitecustomize` stub into the active virtual environment |
| `uninstall-hook` | `selective uninstall-hook` | Uninstalls `.pth` hook stub completely |
| `run` | `selective run <script.py>` | Executes a script with Selective demand loading enabled |

*All CLI commands support `--json` for machine-readable output in CI/CD pipelines.*

---

## 🤝 Relationship to PEP 810 (Python 3.15 Explicit Lazy Imports)

Python 3.15 introduces native explicit lazy imports via PEP 810 (`lazy import json`). 

Selective does not compete with PEP 810—it complements it:
- PEP 810 provides the **mechanism** for lazy imports in code you own.
- Selective provides the **AOT safety analysis** that determines which imports in third-party packages you do not control are safe to make lazy, why, and under what conditions.
- On Python 3.15+, Selective uses PEP 810's `__lazy_modules__` native mechanism directly.

---

## 🛡️ License

Selective is licensed under the Apache 2.0 License.
