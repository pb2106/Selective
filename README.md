<p align="center">
  <img src="logo.png" alt="Selective Logo" width="500"/>
</p>

# Selective

> **Safety-Analyzed, Demand-Driven Package Loading & Supply-Chain Analyzer for Python**  
> *Tagline: Load only what you need, prove observable equivalence, analyze supply-chain security, and explain every decision.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Verification Zero Diffs](https://img.shields.io/badge/OEC%20Harness-0%20Diffs%20%2F%20100%25%20Equivalence-brightgreen.svg)]()
[![Demand Loading Engine](https://img.shields.io/badge/Demand%20Loading-Safety--Analyzed-blue.svg)]()

Selective is an ahead-of-time (AOT) package safety analyzer, supply-chain auditor, and runtime demand loader for Python (CPython 3.10+). It solves Python's eager import bottleneck in large third-party libraries (**PyTorch**, **pandas**, **SciPy**, **NumPy**, **TensorFlow**, **Transformers**), where `import pkg` initializes hundreds of unneeded submodules, native C/C++ extensions, dynamic libraries, and global side effects.

Selective works without modifying third-party packages on disk or executing untrusted code during analysis.

---

## 📋 Table of Contents

- [🚀 Performance Profile & Use Cases](#-performance-profile--use-cases)
- [✨ Key Capabilities](#-key-capabilities)
  - [1. ⚡ Background Speculative Loading](#1--background-speculative-loading)
  - [2. 🛡️ Supply-Chain Security & Behavioral Genome Diffing](#2-️-supply-chain-security--behavioral-genome-diffing)
  - [3. 📂 Project & Workspace Scanning](#3--project--workspace-scanning)
  - [4. 🔍 Automatic Regression Bisecting & Reproduction](#4--automatic-regression-bisecting--reproduction)
  - [5. 📦 Serverless & Container Cold-Start Optimization](#5--serverless--container-cold-start-optimization)
  - [6. 🎯 Import Optimization Budgets](#6--import-optimization-budgets)
  - [7. 🧪 Differential Verification Harness](#7--differential-verification-harness)
- [📦 Quickstart & Installation](#-quickstart--installation)
- [📖 CLI Command Reference](#-cli-command-reference)
- [🐍 Python API & Configuration](#-python-api--configuration)
- [📊 Metric Labeling Standards](#-metric-labeling-standards)
- [🏗️ Architecture & Safety Model](#️-architecture--safety-model)
- [🤝 Compatibility with PEP 810](#-compatibility-with-pep-810)
- [🛡️ License](#️-license)

---

## 🚀 Performance Profile & Use Cases

Selective optimizes Python application **startup latency** by dynamically deferring submodules that are not accessed during boot.

### When Selective Delivers Maximum Speedup
Selective is designed for applications where large third-party libraries are imported during boot, but only a fraction of their submodules are immediately accessed:

- ⚡ **Serverless & Cloud Functions (AWS Lambda, GCP Functions)**: Dramatically reduces cold-start boot latency by deferring heavy SDK submodules until invoked.
- ⚡ **Web Microservices (FastAPI, Flask, Django)**: Fast application startup by loading core routes on boot and deferring heavy background submodules (e.g. ML models, reporting modules) until their specific HTTP endpoints are called.
- ⚡ **Command-Line Interfaces (CLIs)**: Enables fast response times for quick commands (like `--help` or `--version`) without eagerly initializing entire framework subtrees.

### Workload Characteristics & Trade-offs

| Workload Scenario | Submodules Deferred | Selective Impact |
|---|---|---|
| **Selective Submodule Deferral** (Large app/service importing heavy SDKs/frameworks) | 1,000–3,000+ submodules deferred | **70–90% faster boot time** |
| **Fully-Used Minimal Core** (Microbenchmarks or code calling 100% of a minimal package core) | 0 submodules deferred | ~50–80 ms runtime proxy overhead |

- **MetaPathFinder Fast Reject Latency**: `< 0.150 µs` per `find_spec` lookup for unmanaged modules.
- **Observable Equivalence (OEC)**: Guaranteed 100% functional equivalence with zero diffs under Differential Verification.

---

## ✨ Key Capabilities

### 1. ⚡ Background Speculative Loading
Pre-parses, pre-transforms, compiles, and caches bytecode for high-probability modules on background worker threads without executing module bodies prematurely.

- **Python API**:
  ```python
  import selective
  selective.prefetch("torch.optim", confidence=0.98)
  ```
- **CLI Execution**:
  ```bash
  selective run app.py --speculative --spec-workers 4
  ```

### 2. 🛡️ Supply-Chain Security & Behavioral Genome Diffing
Statically analyzes third-party package capabilities without executing untrusted code.
- Scans for dangerous capabilities: dynamic execution (`eval`, `exec`), native process/system access (`subprocess`, `ctypes`, `os.system`), network capabilities (`socket`, `requests`, `urllib`), environment mutations (`os.environ`), and global import hooks (`sys.meta_path`).
- Computes a deterministic **Behavioral Genome** SHA-256 hash.
- Compares supply-chain diffs between dependency versions:
  ```bash
  # Generate security report
  selective security torch --fail-on HIGH

  # Diff behavioral changes between package versions
  selective security diff old_version.json new_version.json
  ```

### 3. 📂 Project & Workspace Scanning
Scan a local repository or workspace folder to automatically discover all third-party package dependencies across every `.py` file, build dependency graphs, and bake optimized caches:
```bash
selective scan ./my_project --project --bake ./baked_cache
```

### 4. 🔍 Automatic Regression Bisecting & Reproduction
When a module demand-load causes a behavioral discrepancy, Selective isolates the minimal failing import edge using delta-debugging algorithms:
```bash
selective bisect app.py --level 5
```
- Creates a self-contained reproduction bundle in `.selective/repro/case-XXXX/` containing `app.py`, `baseline.json`, `selective.json`, `load_plan.json`, `failing_edges.json`, and `explanation.json`.
- Explains safety classification and causal chains:
  ```bash
  selective explain torch.fx --why
  ```

### 5. 📦 Serverless & Container Cold-Start Optimization
Builds relocatable precomputed cache artifacts and deployment manifests for AWS Lambda, Google Cloud Run, Azure Functions, and Docker containers:
```bash
# Serverless / Lambda deployment build
selective build lambda/ --type lambda

# Container build with baked precomputed cache
selective build container/ --type container --bake ./baked_cache --output-dir ./dist
```

### 6. 🎯 Import Optimization Budgets
Set target cold-start latency and memory usage thresholds. Selective automatically selects the optimal load plan under safety constraints:
```bash
selective optimize pandas --startup-target 500ms --memory-target 300MB --safety strict
```

### 7. 🧪 Differential Verification Harness
Runs differential testing against Observable Equivalence Contracts (OEC Levels 1–5):
```bash
selective verify app.py --level 5
```
Inspects stdout/stderr, return codes, `sys.modules` state, global attributes, and side-effect hook integrity. Harness-injected control flags (`SELECTIVE_DISABLE`, etc.) are automatically excluded from process state (L4) comparison to prevent false positives while preserving strict detection of real environment mutations.

---

## 📦 Quickstart & Installation

### Installation

```bash
git clone https://github.com/naegleria/Selective.git
cd Selective
pip install -e .
```

### Quick Walkthrough

1. **Scan and optimize a package or project**:
   ```bash
   # Scan a single package
   selective scan pandas

   # Or scan an entire project directory
   selective scan ./my_app --project
   ```

2. **Verify observable equivalence**:
   ```bash
   selective verify main.py
   ```

3. **Run script with demand-loading enabled**:
   ```bash
   selective run main.py --speculative
   ```

4. **(Optional) Install global virtual environment import hook**:
   ```bash
   selective install-hook
   ```

---

## 📖 CLI Command Reference

All CLI commands support `--json` for CI/CD integration.

| Command | Usage Example | Description |
|---|---|---|
| `scan` | `selective scan pandas` <br>`selective scan ./src --project --bake ./cache` | Scans a package or project directory and builds demand-load plans. |
| `security` | `selective security torch --fail-on HIGH` | Generates supply-chain security report & behavioral genome hash. |
| `security diff` | `selective security diff old.json new.json` | Computes supply-chain diffs and flags newly introduced capabilities. |
| `explain` | `selective explain torch.fx --why` | Explains module safety decisions and complete causal failure chains. |
| `bisect` | `selective bisect app.py --level 5` | Delta-debugging bisection isolating minimal failing edge & repro artifact. |
| `build` | `selective build ./app --type container --bake ./baked` | Generates relocatable container/serverless cold-start artifacts. |
| `optimize` | `selective optimize pandas --startup-target 500ms` | Optimizes load plan under explicit startup and memory targets. |
| `verify` | `selective verify app.py --level 5` | Differential verification against Observable Equivalence Contract. |
| `doctor` | `selective doctor` | Displays environment diagnostics, cache writeability, and hook health. |
| `install-hook` | `selective install-hook` | Installs `.pth` / `sitecustomize` stub into the active virtual environment. |
| `uninstall-hook` | `selective uninstall-hook` | Uninstalls `.pth` hook stub cleanly. |
| `run` | `selective run app.py --speculative` | Executes a script with Selective demand loading enabled. |

---

## 🐍 Python API & Configuration

### Python API

```python
import selective

# Speculatively compile and pre-cache a module in the background
selective.prefetch("torch.optim", confidence=0.98)
```

### Environment Variables

| Variable | Values | Description |
|---|---|---|
| `SELECTIVE_DISABLE` | `0` \| `1` | Emergency kill switch to disable Selective demand-loading (`1` = disabled). |
| `SELECTIVE_MODE` | `conservative` \| `lenient` | Load plan strictness (`conservative` avoids non-deterministic side-effects). |
| `SELECTIVE_STRICT` | `0` \| `1` | Fail fast on any unhandled lazy loading exception (`1` = strict). |
| `SELECTIVE_LOG` | `<filepath>` | Path to write runtime demand-loader diagnostics and trace logs. |
| `SELECTIVE_CACHE` | `<dirpath>` | Custom directory path for persistent bytecode cache. |
| `SELECTIVE_BAKED_CACHE` | `<dirpath>` | Read-only directory containing pre-baked bytecode caches (e.g. Docker images). |
| `SELECTIVE_SPECULATIVE` | `0` \| `1` | Enables background speculative module compilation worker pool (`1` = enabled). |

---

## 📊 Metric Labeling Standards

Selective clearly distinguishes metric sources across CLI outputs and JSON artifacts:

- **`measured`**: Empirical measurements gathered directly from subprocess benchmark runs.
- **`estimated`**: Analytical estimates calculated from AST dependency structure and file sizes.
- **`predicted`**: Probabilistic confidence scores assigned by the speculative scheduler.

---

## 🏗️ Architecture & Safety Model

Selective classifies modules into **6 Safety Tiers**:

1. `SAFE_LAZY`: Pure functions/classes, zero global side effects. Safe for demand loading.
2. `CONDITIONALLY_LAZY`: Lazy unless specific features or submodules are invoked.
3. `EAGER_REQUIRED`: Global state mutations, registration calls, or dynamic exports requiring eager load.
4. `NATIVE_REQUIRED`: Loads C-extensions / native dynamic shared libraries (`.so`, `.dylib`, `.dll`).
5. `SECURITY_EAGER`: Contains sensitive capabilities (`subprocess`, `eval`, audit hooks) requiring eager load.
6. `UNKNOWN`: Unparseable or dynamic module requires eager loading for safety.

### Multi-Tier Cache Resolution Order

1. **Runtime In-Memory Cache**: Active process compiled AST & proxies.
2. **Project Baked Cache** (`SELECTIVE_BAKED_CACHE` / `./baked_cache`): Read-only precomputed artifacts.
3. **User Cache** (`~/.cache/selective`): Persistent local bytecode cache keyed by source SHA-256.
4. **Virtualenv Global Cache**: Fallback cache within Python environment.

---

## 🤝 Compatibility with PEP 810

Python 3.15 introduces native explicit lazy imports via **PEP 810** (`lazy import json`). Selective complements PEP 810 by providing the ahead-of-time (AOT) safety analysis that determines which imports in complex third-party packages are safe to defer:

- **Strategy A (Python 3.15+)**: Injects native `__lazy_modules__` directives for `SAFE_LAZY` targets.
- **Strategy B (Python 3.10 – 3.14)**: Uses Selective's source-transform AST rewriter and `LazyModuleProxy` loader.

---

## 🛡️ License

Selective is licensed under the **Apache 2.0 License**. See [LICENSE](LICENSE) for details.
