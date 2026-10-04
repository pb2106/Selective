# Selective
## Safety-Analyzed, Demand-Driven Package Loading for Python

Selective is an AOT package analyzer and runtime demand loader for Python packages (CPython 3.10+). It analyzes packages statically without executing code, builds persistent dependency and safety graphs, and uses a source-transform loader (or CPython 3.15+ native `__lazy_modules__`) to load components only when accessed.

### Quick Start
```bash
# Install editable
pip install -e .

# Scan a package
selective scan pandas

# Explain import decisions
selective explain pandas

# Run script with Selective optimization
selective run app.py
```
