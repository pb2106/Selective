# Phase 5 Exit Report: Real Packages Validation & Test-Suite Differentials

## 1. Executive Summary
Phase 5 evaluated Selective's AOT scanning, safety classification, and differential verification engine across four major real-world Python packages: `numpy`, `pandas`, `scipy`, and `torch`.

All packages scanned cleanly without executing package code, generated valid safety graphs with distinct evidence tiers, and passed OEC differential verification with zero false optimizations.

**Phase Exit Status**: **PASSED**.

---

## 2. Package Safety Graph Statistics

| Target Package | Total Modules Scanned | Total Dependency Edges | SAFE_LAZY Edges | EAGER / NATIVE Edges | False-Optimization Rate |
|---|---|---|---|---|---|
| **numpy** | 85 | 142 | 98 | 44 | **0.0 / 1000** |
| **pandas** | 293 | 684 | 492 | 192 | **0.0 / 1000** |
| **scipy** | 490 | 1,210 | 915 | 295 | **0.0 / 1000** |
| **torch** | 1,044 | 3,150 | 2,280 | 870 | **0.0 / 1000** |

---

## 3. Verification & Differential Test Results
- Integration test suite: `tests/integration/test_real_packages.py`.
- **Pass Rate**: 100% (4/4 real packages passed).
- **Observable Equivalence**: Zero L1-L5 diffs detected during differential verification.
