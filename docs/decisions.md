# Architecture Decision Records (ADRs)

## ADR-001: Language Target and Python Version Strategy
- **Status**: Accepted
- **Context**: Selective targets CPython 3.10+. Python 3.15 adds native explicit lazy imports (PEP 810).
- **Decision**: Selective will support two runtime strategies:
  1. **Strategy A (Native)**: On CPython 3.15+, the loader injects a generated `__lazy_modules__` list into module ASTs before execution, using Python's native lazy import mechanism.
  2. **Strategy B (Source Transform)**: On CPython 3.10-3.14, the loader transforms module ASTs by converting module-scope imports into lazy stub descriptors and modifying module `__getattr__` and `__dir__` (PEP 562).
- **Consequences**: Unified safety analysis engine for all Python versions, leveraging native performance on 3.15+ while remaining fully functional on existing Python versions.

## ADR-002: Modular Granularity & Symbol Binding Tables
- **Status**: Accepted
- **Context**: Function-level slicing of third-party packages is fragile and unsafe due to cross-module references and dynamic bindings.
- **Decision**: Loading decisions operate strictly at **module granularity**. A symbol binding table is recorded per module to map public exports and re-exports to their source modules, enabling precise lazy lookup generation and detailed explanations.
- **Consequences**: Standard Python module semantics are preserved; lazy module stubs resolve on first attribute access.

## ADR-003: AOT Static-Only Analysis (No Code Execution)
- **Status**: Accepted
- **Context**: Dynamic execution of package code during analysis can trigger security risks, unwanted side effects, hardware checks, or state mutations.
- **Decision**: The offline analyzer (`selective scan`) relies strictly on static AST parsing and binary library inspection. Package code is never executed during scanning.
- **Consequences**: Analysis is safe and deterministic. Any construct that cannot be proven safe statically defaults to `UNKNOWN` (kept eager under conservative policy).

## ADR-004: Thread Safety and Degradation Ladder
- **Status**: Accepted
- **Context**: Concurrent attribute access on lazy module stubs in multi-threaded environments can lead to race conditions or duplicate import execution.
- **Decision**: Miss path resolution is guarded by per-module reentrant locks with strict lock ordering to prevent deadlocks. If a lazy resolution fails or violates graph expectations, Selective degrades by marking the package as process-tainted, forcing remaining stubs to resolve eagerly.
- **Consequences**: Thread-safe execution; analysis errors impact speed rather than program correctness.
