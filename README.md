<p align="center">
  <img src="logo.png" alt="Selective Logo" width="500"/>
</p>

# Selective

> **Safety-Analyzed, Demand-Driven Package Loading & Optimization for Python**  
> *Tagline: Load only what you need, prove observable equivalence, analyze supply-chain security, and explain every decision.*

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

## 🛠️ Extended Capabilities

### 1. ⚡ Background Speculative Loading
Prepares likely-needed modules in the background (AST parsing, transforming, bytecode compilation, and caching) while application execution continues without changing observable behavior:
```python
import selective
selective.prefetch("torch.optim", confidence=0.98)
```
Or enable background speculative loading via CLI:
```bash
selective run app.py --speculative
```

### 2. 🛡️ Supply-Chain Security Analysis
Analyzes dependency capabilities statically without executing untrusted code:
- Detects dynamic code execution (`eval`, `exec`, `importlib.import_module`), system interactions (`subprocess`, `ctypes`, `os.system`), network capabilities (`socket`, `requests`, `urllib`), environment mutations (`os.environ`), and global import hooks (`sys.meta_path`).
- Generates a stable **Behavioral Genome** hash (`genome_id`).
- Compares supply-chain changes between package versions:
```bash
# Security report for package
selective security torch --fail-on HIGH

# Supply-chain diff between versions
selective security diff torch-v1.json torch-v2.json
```

### 3. 🔍 Automatic Regression Bisecting & Reproduction
Automatically isolates the minimal lazy-import edge causing an OEC verification regression using delta-debugging:
```bash
selective bisect app.py
```
- Generates a deterministic reproduction directory `.selective/repro/case-XXXX/` containing `app.py`, `baseline.json`, `selective.json`, `load_plan.json`, `failing_edges.json`, and `explanation.json`.
- Explains causal chains:
```bash
selective explain torch.fx --why
```

### 4. 📦 Serverless & Container Optimization
Optimizes Python cold-starts for AWS Lambda, Google Cloud Run, Azure Functions, and Docker containers:
```bash
selective build lambda/ --type lambda
selective build container/ --type container --bake ./baked_cache
```
Generates relocatable precomputed cache artifacts and `build_manifest.json`.

### 5. 🎯 Import Optimization Budgets
Allows developers to set explicit performance constraints and optimizes load plans under safety strictness:
```bash
selective optimize pandas --startup-target 500ms --memory-target 300MB --safety strict
```
Enforces safety as a hard constraint and provides explainable decisions for blocking modules.

---

## 📖 CLI Command Reference

| Command | Usage | Description |
|---|---|---|
| `scan` | `selective scan [target] [--project] [--bake DIR]` | Scans a package or project directory and auto-discovers dependencies |
| `security` | `selective security <pkg> [--fail-on LEVEL]` | Generates supply-chain security report & behavioral genome |
| `security diff` | `selective security diff <old.json> <new.json>` | Diffs supply-chain behavioral changes between two report JSONs |
| `explain` | `selective explain <module> [--unsafe] [--why]` | Explains import safety decisions or complete causal failure chains |
| `bisect` | `selective bisect <script.py>` | Delta-debugging bisection isolating minimal failing edge & repro artifact |
| `build` | `selective build <target> [--type container\|lambda]` | Precomputes relocatable container/serverless cold-start artifacts |
| `optimize` | `selective optimize <target> [--startup-target 500ms]` | Optimizes load plan under explicit startup and memory budgets |
| `verify` | `selective verify <script.py>` | Runs differential subprocess verification against OEC contract |
| `doctor` | `selective doctor` | Displays environment diagnostics, cache writeability, and hook health |
| `install-hook` | `selective install-hook` | Installs `.pth` / `sitecustomize` stub into the active virtual environment |
| `uninstall-hook` | `selective uninstall-hook` | Uninstalls `.pth` hook stub completely |
| `run` | `selective run <script.py> [--speculative]` | Executes a script with Selective demand loading and optional speculation |

*All CLI commands support `--json` for machine-readable output in CI/CD pipelines.*

---

## 📊 Performance Metric Labels

Selective clearly distinguishes metric sources across CLI outputs and JSON artifacts:
- **`measured`**: Empirical measurements gathered directly from subprocess benchmark runs.
- **`estimated`**: Analytical estimates calculated from AST dependency structure and file sizes.
- **`predicted`**: Probabilistic confidence scores assigned by the speculative scheduler.

---

## 🤝 Relationship to PEP 810 (Python 3.15 Explicit Lazy Imports)

Python 3.15 introduces native explicit lazy imports via PEP 810 (`lazy import json`). Selective complements PEP 810 by providing the AOT safety analysis that determines which imports in third-party packages are safe to make lazy, and uses PEP 810's native `__lazy_modules__` mechanism on 3.15+.

---

## 🛡️ License

Selective is licensed under the Apache 2.0 License.
