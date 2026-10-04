# Assumptions and Clarifications

## 1. Environment & Runtime Assumptions
1. **CPython Version**: The runtime operates on CPython 3.10+ (specifically tested on CPython 3.13 in this workspace).
2. **Standard Library Scope**: The standard library modules are excluded from lazy transformation in v1 unless explicitly pulled in as a dependency edge by a managed third-party package.
3. **Single Process State**: Each Python subprocess manages its own cache state and fast-reject finder list. Subprocesses spawned via `multiprocessing` inherit configuration flags via environment variables.

## 2. Dynamic Python Constructs & Safety Bounds
1. **`try/except ImportError` Feature Probes**: Probes checking module availability (e.g. `try: import scipy except ImportError: ...`) are kept eager by default unless rewritten into non-importing spec checks (`importlib.util.find_spec`).
2. **Star Imports (`from pkg import *`)**: Never made lazy; left eager in accordance with PEP 810 guidelines.
3. **Dynamic `__import__` / `importlib.import_module`**: If the module name argument is non-constant, the call is classified `UNKNOWN` and kept eager.
4. **Metaclass Registration Side Effects**: Modules with metaclass definitions that execute side effects at module creation time are classified `EAGER_REQUIRED`.

## 3. Package Identity & Cache Invalidation
1. **Fingerprint Hash**: Includes package name, version, file hashes (`RECORD` or source file sha256), ABI tag, GIL mode, OS, Python version, and analyzer/transform version.
2. **Read-Only Environments**: In read-only filesystems (e.g. AWS Lambda), cache writes are silently bypassed; if no pre-baked cache exists, execution falls back safely to plain eager imports.
