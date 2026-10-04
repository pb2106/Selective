# Selective: Development Plan & System Architecture

## 1. Overview
Selective is a safety-analyzed, demand-driven package loading optimizer for Python (CPython 3.10+). It performs ahead-of-time (AOT) static safety analysis of Python packages without executing code, builds persistent dependency and safety graphs, and uses a source-transform loader (or Python 3.15+ native `__lazy_modules__`) to load package modules on demand.

This document defines the architectural boundaries, directory layout, phase progression, and exit criteria.

---

## 2. Directory Layout & Module Boundaries

```text
Selective/
├── docs/                        # Architectural documents, decisions, and phase reports
│   ├── plan.md                  # This file
│   ├── decisions.md             # Architecture Decision Records (ADRs)
│   ├── assumptions.md           # Explicit assumptions and clarifications
│   ├── limitations.md           # Known bounds and explicit non-goals
│   └── phase-N-report.md        # Individual phase completion reports (0 through 7)
├── selective/                   # Primary Python package
│   ├── __init__.py              # Package version & top-level exports
│   ├── analyzer/                # AOT Analysis Engine (No code execution)
│   │   ├── __init__.py
│   │   ├── scanner.py           # Parallel/incremental file scanner & AST parser
│   │   ├── import_extractor.py  # AST import statement extractor & branch analyzer
│   │   ├── static_pruner.py     # TYPE_CHECKING, sys.version/platform static eliminations
│   │   ├── side_effects.py      # AST side-effect detector & evidence tiering
│   │   ├── native_scanner.py    # ELF/Mach-O/PE binary & PyInit extension scanner
│   │   ├── symbol_table.py      # Symbol binding & re-export resolution table
│   │   ├── classifier.py        # Safety classification engine (SAFE_LAZY, EAGER, etc.)
│   │   ├── graph_builder.py     # Static (A), Safety (B), & Runtime Plan (C) builder
│   │   └── serializer.py        # Graph serialization & fast mmap-friendly binary format
│   ├── loader/                  # Demand-Driven Runtime Loader Engine
│   │   ├── __init__.py
│   │   ├── finder.py            # SelectiveFinder MetaPathFinder with O(1) fast reject
│   │   ├── transformer.py       # Strategy B AST Rewriter & Strategy A __lazy_modules__ injector
│   │   ├── cache_manager.py     # Bytecode cache (source hash + graph_id + magic)
│   │   ├── loader.py            # SelectiveLoader (subclassing importlib SourceLoader)
│   │   ├── miss_path.py         # Thread-safe late loader, per-module lock & degradation ladder
│   │   └── controls.py          # Environment variables & runtime switches (SELECTIVE_*)
│   ├── harness/                 # Differential Verification & Equivalence Engine
│   │   ├── __init__.py
│   │   ├── oec.py               # Observable Equivalence Contract (L1-L5) snapshotter
│   │   ├── verify.py            # Subprocess differential verification runner
│   │   ├── fuzzer.py            # Import & attribute access order randomizer
│   │   ├── bisect.py            # Monotonic edge bisection engine
│   │   └── adapters/            # Package-specific snapshot adapters (torch, pandas, stdlib)
│   ├── deploy/                  # Deployment & Environment Integration
│   │   ├── __init__.py
│   │   ├── cache_resolver.py    # Multi-tier cache path resolution & read-only fallback
│   │   ├── hook.py              # sitecustomize / .pth hook installer & uninstaller
│   │   └── preload.py           # Pre-fork expected-use set preloader
│   └── cli/                     # Command-Line Interface (`selective`)
│       ├── __init__.py
│       ├── main.py              # Main CLI entrypoint
│       └── commands.py          # Implementations of scan, graph, explain, verify, bisect, etc.
├── tests/                       # Automated Test Suite
│   ├── unit/                    # Unit tests for scanner, loader, transformer, miss_path, etc.
│   ├── integration/             # Integration tests for real packages
│   └── harness_tests/           # Tests for the verification harness itself
├── benchmarks/                  # Baselines & Benchmark Suite
│   ├── workloads/               # Target package workloads (A tiny, B medium, C broad)
│   └── runner.py                # Automated benchmark execution & PSS/timing reporter
└── pyproject.toml               # Package configuration & entrypoints
```

---

## 3. Detailed Phase Breakdown & Exit Criteria

### Phase 0: Feasibility Gate
- **Tasks**:
  1. Measure `-X importtime` profiles for `pandas`, `scipy`, `numpy`, `torch` across defined workloads.
  2. Perform Oracle experiment to quantify maximum theoretical savings `upper_bound_savings`.
  3. Construct a hand-crafted lazy import prototype on a real target package.
  4. Compare `upper_bound_savings` against feasibility threshold.
- **Exit Criteria**: `docs/phase-0-report.md` published with measured upper bounds and decision gate sign-off.

### Phase 1: Package Scanner & AST Importer
- **Tasks**:
  1. Implement parallel, file-hash incremental package file scanner.
  2. Implement AST import extractor.
  3. Implement static elimination of `if TYPE_CHECKING:`, constant platform/version branches, and dead code.
  4. Implement basic graph model and JSON serializer.
- **Exit Criteria**: `selective scan <package>` successfully produces static graphs for test packages without executing package code. Unit test coverage > 90%.

### Phase 2: Graph Depth, Symbol Tables & Serialization
- **Tasks**:
  1. Resolve relative and dynamic import nodes.
  2. Build symbol binding tables per module (exports, re-exports).
  3. Implement composable cross-package graph references.
  4. Implement fast binary serialization format for runtime mmap deserialization.
- **Exit Criteria**: Multi-package graphs serialized and restored with < 5ms deserialization overhead.

### Phase 3: Safety Analysis, Side-Effect Analyzer & Native Binary Scanner
- **Tasks**:
  1. AST side-effect analyzer (registration calls, decorators, atexit/signal/threading, os.environ, warnings/logging, audit hooks).
  2. Binary scanner using `pyelftools` for shared library `DT_NEEDED`/`RPATH` dependencies + PyInit string inspection.
  3. Evidence tier classification engine (`SAFE_LAZY`, `CONDITIONALLY_LAZY`, `EAGER_REQUIRED`, `NATIVE_REQUIRED`, `SECURITY_EAGER`, `UNKNOWN`).
- **Exit Criteria**: Safety graph generated with explicit evidence tiers for target packages without false lazy classifications on side-effectful modules.

### Phase 3.5: Differential Verification Harness (Required Before Phase 4)
- **Tasks**:
  1. Implement Observable Equivalence Contract (OEC) Snapshotter for L1 (Namespace), L2 (Registries), L3 (Behavior), L4 (Process State), L5 (Error Timing).
  2. Implement subprocess differential runner `selective verify`.
  3. Implement import & attribute access order fuzzer.
  4. Implement monotonic edge bisection engine `selective bisect`.
- **Exit Criteria**: `selective verify` cleanly catches injected synthetic regressions across all 5 levels.

### Phase 4: Source-Transform Loader & Miss Path
- **Tasks**:
  1. Implement `SelectiveFinder` with fast-reject set & fast fingerprint check.
  2. Implement Strategy B AST transformer (rewriting lazy imports, creating lazy stubs, updating module `__getattr__`/`__dir__`, preserving source line numbers/inspect/linecache).
  3. Implement Strategy A native `__lazy_modules__` injector for Python 3.15+.
  4. Implement transformed bytecode cache manager.
  5. Implement thread-safe Miss Path with per-module locks, cycle detection, graph violation checks, and degradation ladder (process tainting, eager fallback, hint persistence).
- **Exit Criteria**: `selective run` executes target scripts using transformed code, triggering late loads transparently on demand and passing `selective verify`.

### Phase 5: Real Packages Validation & Test-Suite Differentials
- **Tasks**:
  1. Run `selective verify` on `pandas`, `scipy`, `numpy`, `torch`.
  2. Execute upstream test suites of managed packages under Selective strict mode.
  3. Fix any discovered safety edge classifications via evidence tier refinement.
- **Exit Criteria**: Zero L1-L5 diffs on supported packages; false-optimization rate recorded.

### Phase 6: Deployment, Baking & Preload Integration
- **Tasks**:
  1. Implement multi-tier cache location resolution (including read-only fallback).
  2. Implement `--bake` for relocatable container/serverless deployment.
  3. Implement `install-hook` / `uninstall-hook` for `.pth` / `sitecustomize` integration.
  4. Implement `preload` pre-fork expected-use set preloading.
  5. Implement `selective doctor`.
- **Exit Criteria**: Containerized and pre-fork server workflows tested and validated.

### Phase 7: Benchmarks, CLI Polish & Documentation
- **Tasks**:
  1. Execute benchmark suite across Workloads A, B, C under cold/warm conditions.
  2. Measure startup time, PSS memory, first-use latency, hook microbenchmarks, stub overhead.
  3. Complete CLI commands (`explain`, `graph`, `report`, `inspect`, etc.) with `--json` support.
  4. Generate final reports and documentation.
- **Exit Criteria**: All success criteria from PRD Section 17.6 verified and documented in `docs/phase-7-report.md`.
