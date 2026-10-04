"""
Observable Equivalence Contract (OEC) Snapshot Engine for Selective.
Captures snapshots across L1 (Namespace), L2 (Registries), L3 (Behavior), L4 (Process State), L5 (Error Timing).
"""

import sys
import os
import inspect
import json
import warnings
import logging
from typing import Dict, Any, List, Set, Tuple

class OECSnapshot:
    def __init__(
        self,
        l1_namespaces: Dict[str, List[str]],
        l2_registries: Dict[str, Any],
        l3_behavior: Dict[str, Any],
        l4_process_state: Dict[str, Any],
        l5_error_timing: Dict[str, Any],
    ):
        self.l1_namespaces = l1_namespaces
        self.l2_registries = l2_registries
        self.l3_behavior = l3_behavior
        self.l4_process_state = l4_process_state
        self.l5_error_timing = l5_error_timing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "L1_Namespace": self.l1_namespaces,
            "L2_Registries": self.l2_registries,
            "L3_Behavior": self.l3_behavior,
            "L4_ProcessState": self.l4_process_state,
            "L5_ErrorTiming": self.l5_error_timing,
        }

    def diff(self, other: "OECSnapshot") -> Dict[str, Any]:
        diffs = {}
        
        # L1 Diff
        l1_diff = {}
        all_mods = set(self.l1_namespaces.keys()) | set(other.l1_namespaces.keys())
        for mod in sorted(all_mods):
            names_a = set(self.l1_namespaces.get(mod, []))
            names_b = set(other.l1_namespaces.get(mod, []))
            if names_a != names_b:
                l1_diff[mod] = {
                    "only_in_baseline": list(names_a - names_b),
                    "only_in_target": list(names_b - names_a),
                }
        if l1_diff:
            diffs["L1_Namespace"] = l1_diff

        # L2 Diff
        if self.l2_registries != other.l2_registries:
            diffs["L2_Registries"] = {
                "baseline": self.l2_registries,
                "target": other.l2_registries,
            }

        # L3 Diff
        if self.l3_behavior != other.l3_behavior:
            diffs["L3_Behavior"] = {
                "baseline": self.l3_behavior,
                "target": other.l3_behavior,
            }

        # L4 Diff
        l4_diff = {}
        for k in set(self.l4_process_state.keys()) | set(other.l4_process_state.keys()):
            val_a = self.l4_process_state.get(k)
            val_b = other.l4_process_state.get(k)
            if val_a != val_b:
                l4_diff[k] = {"baseline": val_a, "target": val_b}
        if l4_diff:
            diffs["L4_ProcessState"] = l4_diff

        # L5 Diff
        if self.l5_error_timing != other.l5_error_timing:
            diffs["L5_ErrorTiming"] = {
                "baseline": self.l5_error_timing,
                "target": other.l5_error_timing,
            }

        return diffs

class OECSnapshotEngine:
    @staticmethod
    def capture(managed_package_names: List[str]) -> OECSnapshot:
        # L1: Namespace
        l1: Dict[str, List[str]] = {}
        for mod_name, mod_obj in list(sys.modules.items()):
            if any(mod_name == pkg or mod_name.startswith(pkg + ".") for pkg in managed_package_names):
                if mod_obj is not None:
                    try:
                        dir_names = sorted(dir(mod_obj))
                        l1[mod_name] = dir_names
                    except Exception:
                        pass

        # L2: Registries (pandas accessors, torch ops if imported, etc.)
        l2: Dict[str, Any] = {}
        if "pandas" in sys.modules:
            try:
                import pandas as pd
                l2["pandas_series_accessors"] = list(getattr(pd.Series, "_accessors", set()))
                l2["pandas_dataframe_accessors"] = list(getattr(pd.DataFrame, "_accessors", set()))
            except Exception:
                pass
        if "torch" in sys.modules:
            try:
                import torch
                l2["torch_ops_count"] = len(getattr(torch.ops, "_op_list", [])) if hasattr(torch.ops, "_op_list") else 0
            except Exception:
                pass

        # L3: Behavior (placeholder for execution output / return values)
        l3 = {"status": "ok"}

        # L4: Process State
        l4 = {
            "env_vars": dict(os.environ),
            "sys_path_len": len(sys.path),
            "recursion_limit": sys.getrecursionlimit(),
        }

        # L5: Error Timing
        l5 = {"error": None}

        return OECSnapshot(l1, l2, l3, l4, l5)
