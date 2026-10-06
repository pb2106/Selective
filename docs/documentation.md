# Selective: Technical Architecture & User Guide

> **Version:** 2.0  
> **Target:** CPython 3.10+ (Native PEP 810 Fast-Path on CPython 3.15+)  
> **License:** Apache 2.0  

---

## 1. Executive Summary & Core Objective

**Selective** is an ahead-of-time (AOT) package safety analyzer, supply-chain auditor, and runtime demand loader for Python. It addresses Python's eager import bottleneck in large data science and machine learning packages (**PyTorch**, **pandas**, **SciPy**, **NumPy**, **TensorFlow**, **Transformers**), where `import pkg` initializes hundreds of submodules, native dynamic C/C++ shared libraries, global side effects, and registration decorators that a program never invokes.

Selective operates under a strict constraint: **Never sacrifice safety for performance targets.** It achieves up to **97.1% startup import overhead reduction** without modifying installed packages on disk or executing untrusted third-party code during AOT analysis.

---

## 2. System Architecture & Module Map

The Selective codebase is structured into five core sub-packages:

```
selective/
├── analyzer/              # AOT Static Analysis & Safety Graph Engine
│   ├── scanner.py          # Package & Project Directory Scanner (AST & ELF)
│   ├── import_extractor.py # AST Import Extractor & Relative Import Resolver
│   ├── static_pruner.py    # Zero-risk static elimination (TYPE_CHECKING, platform/version)
│   ├── symbol_table.py    # Symbol binding & __all__ export resolver
│   ├── side_effects.py    # AST side-effect analyzer (registration, hooks, env writes)
│   ├── native_scanner.py  # ELF dynamic section scanner (pyelftools: DT_NEEDED, PyInit_*)
│   ├── classifier.py      # Safety classifier (6 evidence tiers)
│   ├── graph_builder.py   # Dependency Graphs (Static A, Safety B, Runtime Plan C)
│   ├── serializer.py      # JSON & binary SLTV graph serialization
│   ├── security.py        # Supply-Chain Security & Behavioral Genome Generator
│   └── budget_optimizer.py# Budget Optimizer (Startup & Memory targets under safety)
│
├── loader/                # Runtime Demand Loader & Bytecode Transformer
│   ├── finder.py          # SelectiveFinder (O(1) MetaPathFinder fast reject)
│   ├── transformer.py     # Strategy B (AST Proxy Rewriter) & Strategy A (PEP 810 __lazy_modules__)
│   ├── loader.py          # SelectiveLoader (SourceLoader serving transformed bytecode)
│   ├── cache_manager.py   # Bytecode cache manager keyed by sha256(source + graph_id + MAGIC)
│   ├── miss_path.py       # Thread-safe LazyModuleProxy & Process Tainting engine
│   ├── speculative.py     # Background Speculative Scheduler & Worker Pool
│   └── controls.py        # Environment flags & runtime configuration
│
├── harness/               # Verification, Bisection, and Fuzzing
│   ├── oec.py             # Observable Equivalence Contract snapshot engine (L1–L5)
│   ├── verify.py          # Differential Subprocess Verifier
│   ├── fuzzer.py          # Import & Attribute Access Order Randomizer
│   └── bisect.py          # Advanced Delta-Debugging Bisector & Repro Generator
│
├── deploy/                # Deployment, Building, and Diagnostics
│   ├── cache_resolver.py  # Multi-tier cache resolver & read-only filesystem handling
│   ├── hook.py            # .pth / sitecustomize virtualenv hook installer
│   ├── preload.py         # Pre-fork expected-use set preloader
│   ├── doctor.py          # System environment diagnostics
│   └── builder.py         # SelectiveArtifactBuilder for serverless & container builds
│
└── cli/                   # Command Line Interface
    ├── commands.py        # CLI subcommand implementations
    └── main.py            # CLI entry point parser
```

---

## 3. Safety Classification Framework

Selective classifies every module and import edge into **6 Safety Tiers**:

| Safety Class | Evidence Tier | Description | Strategy |
|---|---|---|---|
| `SAFE_LAZY` | Tier 1 / Tier 2 | Pure module body with defs, classes, and safe imports. No global side effects. | Demand Loaded (Lazy Proxy or PEP 810) |
| `CONDITIONALLY_LAZY` | Tier 3 | Pure body, but conditionally imports modules based on feature invocation. | Demand Loaded with guarded resolution |
| `EAGER_REQUIRED` | Tier 4 | Contains module-scope side effects (registration calls, `@register`, `sys.modules` mutation, `os.environ` writes). | Eager Loaded at startup |
| `NATIVE_REQUIRED` | Tier 4 | Loads native compiled dynamic C/C++ extensions (`.so`, `.pyd`, `.dylib`, `DT_NEEDED`). | Eager Loaded at startup |
| `SECURITY_EAGER` | Tier 4 | Contains security configurations (`sys.addaudithook`) or dynamic execution (`eval`, `exec`). | Eager Loaded at startup |
| `UNKNOWN` | Tier 3 | Unproven dynamic safety under conservative policy. | Default Eager Loaded |

---

## 4. Key Extended Capabilities

### 4.1. Background Speculative Loading Engine
- **Module**: `selective.loader.speculative`
- **Mechanism**: Maintains a priority queue of high-probability target modules based on static usage graphs or explicit confidence scores (`selective.prefetch("torch.optim", confidence=0.98)`).
- **Invariant**: Background worker threads pre-parse ASTs, apply transformations, compile bytecode, and cache results in memory/disk **without executing module bodies (`exec()`) prematurely**.

### 4.2. Supply-Chain Security & Behavioral Genome Hashing
- **Module**: `selective.analyzer.security`
- **Mechanism**: Statically inspects AST nodes and native library headers to detect capabilities:
  - Dynamic Execution (`eval`, `exec`, `importlib`)
  - System Access (`subprocess`, `ctypes`, `os.system`)
  - Network Interfaces (`socket`, `requests`, `urllib`)
  - Environment Mutations (`os.environ`)
  - Audit Hooks (`sys.addaudithook`)
- Computes a stable **Behavioral Genome** SHA-256 hash. Enables differential supply-chain diffing between package versions (`selective security diff old.json new.json`).

### 4.3. Automatic Regression Bisecting & Reproduction
- **Module**: `selective.harness.bisect`
- **Mechanism**: When an OEC verification regression occurs, the `AdvancedBisector` executes delta-debugging algorithms to isolate the minimal failing lazy-import edge.
- **Artifacts**: Generates a self-contained reproduction bundle in `.selective/repro/case-XXXX/` containing:
  - `app.py`: Target script
  - `baseline.json` & `selective.json`: Execution snapshots
  - `failing_edges.json`: Isolated regression edges
  - `explanation.json`: Causal chain explanation (`selective explain --why`)

### 4.4. Serverless & Container Build Optimization
- **Module**: `selective.deploy.builder`
- **Mechanism**: Precomputes transformed bytecode caches and relocatable artifacts for AWS Lambda, Cloud Run, Azure Functions, and Docker containers (`selective build`). Supports `SELECTIVE_BAKED_CACHE` for read-only container layers.

### 4.5. Import Optimization Budgets
- **Module**: `selective.analyzer.budget_optimizer`
- **Mechanism**: Optimizes load plans under developer-specified constraints (`--startup-target 500ms`, `--memory-target 300MB`) while treating safety as a hard non-negotiable constraint.

---

## 5. CLI Command Reference

All CLI commands support `--json` for machine-readable output in CI/CD pipelines.

| Command | Syntax | Description |
|---|---|---|
| `scan` | `selective scan <pkg\|dir> [--project] [--bake DIR]` | Scans package or project directory and builds demand-load graph. |
| `security` | `selective security <pkg> [--fail-on LEVEL]` | Generates supply-chain security report & behavioral genome hash. |
| `security diff` | `selective security diff <old.json> <new.json>` | Diffs supply-chain changes between dependency versions. |
| `explain` | `selective explain <module> [--why] [--unsafe]` | Explains safety decisions and causal failure chains. |
| `bisect` | `selective bisect <script.py> [--level LEVEL]` | Delta-debugging bisection isolating minimal failing edge & repro artifact. |
| `build` | `selective build <target> [--type container\|lambda]` | Precomputes relocatable container/serverless cold-start artifacts. |
| `optimize` | `selective optimize <target> [--startup-target 500ms]` | Optimizes load plan under explicit startup and memory budgets. |
| `verify` | `selective verify <script.py> [--level LEVEL]` | Runs differential subprocess verification against OEC contract. |
| `doctor` | `selective doctor` | Displays environment diagnostics, cache writeability, and hook health. |
| `install-hook` | `selective install-hook` | Installs `.pth` / `sitecustomize` stub into active virtual environment. |
| `uninstall-hook` | `selective uninstall-hook` | Uninstalls `.pth` hook stub completely. |
| `run` | `selective run <script.py> [--speculative]` | Executes a script with Selective demand loading enabled. |

---

## 6. Python API & Environment Controls

### Python API Usage

```python
import selective

# Background speculative compilation & bytecode pre-caching
selective.prefetch("torch.optim", confidence=0.98)
```

### Environment Variables

| Variable | Default | Values | Description |
|---|---|---|---|
| `SELECTIVE_DISABLE` | `0` | `0` \| `1` | Emergency kill switch to disable Selective loader. |
| `SELECTIVE_MODE` | `conservative` | `conservative` \| `lenient` | Safety policy strictness. |
| `SELECTIVE_STRICT` | `0` | `0` \| `1` | Fail fast on unhandled lazy import exception. |
| `SELECTIVE_LOG` | `None` | `<filepath>` | Diagnostic log file path. |
| `SELECTIVE_BAKED_CACHE` | `None` | `<dirpath>` | Read-only pre-baked container cache path. |
| `SELECTIVE_SPECULATIVE` | `0` | `0` \| `1` | Enable background speculative compilation. |

---

## 7. Performance & Verification Metrics

- **Startup Acceleration**: Up to **97.1% faster initial imports** (PyTorch Adam: 2.327s -> 0.067s; SciPy stats: 1.068s -> 0.068s; pandas: 0.470s -> 0.082s).
- **Finder Overhead**: `< 0.150 µs` per `find_spec` lookup on unmanaged imports.
- **OEC Verification Rate**: **0.0 / 1000** false optimizations across full differential verification suite.
