# Explicit Limitations & Non-Goals

1. **Native C/C++ Extensions Slicing**: Selective does not alter or slice inside compiled `.so`, `.dylib`, or `.dll` binary libraries. Native modules marked `NATIVE_REQUIRED` remain eager and preserve their load order.
2. **Permanent Disk Modification**: Selective never modifies installed packages in `site-packages` on disk. Transformed bytecode is served dynamically in memory or stored in Selective's isolated cache directory.
3. **CPython Compute Speedup**: Selective optimizes import initialization time and RSS/PSS memory usage; it does not accelerate underlying Python bytecode execution or C/GPU compute routines.
4. **PyPy and Free-Threaded CPython (v1)**: v1 focuses on CPython 3.10-3.15 standard builds. Free-threaded CPython (3.13t) and PyPy are non-goals for v1.
5. **Star Imports & Dynamic Exec**: Statements like `from foo import *` or `exec("import bar")` are not deferred.
6. **Full-Coverage Minimal Workloads**: Workloads or microbenchmarks that access 100% of a minimal library's core submodules on boot cannot defer submodules, and incur ~50–80 ms of runtime proxy initialization overhead.
