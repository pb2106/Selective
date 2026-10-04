# Phase 3.5 Exit Report: Differential Verification Harness

## 1. Executive Summary
Phase 3.5 implemented the differential testing and equivalence verification harness required before building the runtime loader.

It enforces the Observable Equivalence Contract (OEC) across 5 levels: L1 (Namespace), L2 (Registries), L3 (Behavior), L4 (Process State), and L5 (Error Timing).

**Phase Exit Status**: **PASSED**.

---

## 2. Implemented Components
1. **OEC Snapshot Engine (`selective/harness/oec.py`)**:
   - Captures module namespaces (`dir()`), package registry tables (pandas accessors, torch ops), process environment state, warnings/logging filters, and error conditions.
   - Computes structured diffs between baseline (normal Python) and target (Selective) runs.
2. **Differential Verifier (`selective/harness/verify.py`)**:
   - Executes user scripts in isolated subprocesses under normal Python vs Selective optimization (`selective verify`).
3. **Import Fuzzer (`selective/harness/fuzzer.py`)**:
   - Shuffles module import and attribute access orders to detect circular dependency or order-dependent registration bugs.
4. **Monotonic Edge Bisector (`selective/harness/bisect.py`)**:
   - Monotonically bisects lazy edges to isolate the exact minimal edge causing a differential violation and pins it `EAGER_REQUIRED`.

---

## 3. Verification & Test Results
- Unit test suite: `tests/unit/test_harness.py`.
- **Pass Rate**: 100% (13/13 unit tests passed).
- **Harness Validation**: Verified exact detection of L1 namespace diffs and automated bisection edge isolation.
