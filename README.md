# Selective
## Safety-Analyzed, Demand-Driven Package Loading for Python

Selective is an AOT package analyzer and runtime demand loader for Python packages (CPython 3.10+). It analyzes packages statically without executing code, builds persistent dependency and safety graphs, and uses a source-transform loader (or CPython 3.15+ native `__lazy_modules__`) to load components only when accessed.

### Quick Start

```bash
# Install editable
pip install -e .

# Scan an entire project folder (auto-discovers third-party dependencies)
selective scan /path/to/my_project --project

# Scan a single package
selective scan pandas

# Explain import safety decisions
selective explain pandas

# Run script with Selective optimization
selective run app.py
```

### Features

1. **Project-Aware Scanning (`selective scan --project`)**: Scans all `.py` files in a project folder, extracts used third-party packages, and builds safety graphs for the complete project dependency set.
2. **AOT Safety Analysis**: Analyzes ASTs and shared libraries (`pyelftools`) statically without executing package code.
3. **Source-Transform Loader**: Transforms safe module-scope imports into demand-driven lazy descriptors (Strategy B for CPython < 3.15, Strategy A `__lazy_modules__` for CPython 3.15+).
4. **Differential Verification Harness (`selective verify`)**: Enforces Observable Equivalence Contracts (L1 Namespace, L2 Registries, L3 Behavior, L4 Process State, L5 Error Timing).
5. **Deployment Baking & Hooks**: Relocatable cache baking (`--bake`), pre-fork preloading (`selective preload`), `.pth` integration, and diagnostics (`selective doctor`).
