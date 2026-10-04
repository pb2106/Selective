"""
Import and Attribute Access Order Fuzzer for Selective.
Randomly shuffles module import and attribute access orders to test circular-import & order-dependent registration stability.
"""

import sys
import random
import importlib
from typing import List, Dict, Any
from selective.harness.oec import OECSnapshotEngine

class ImportFuzzer:
    def __init__(self, package_name: str, seed: int = 42):
        self.package_name = package_name
        self.seed = seed
        random.seed(seed)

    def run_fuzz_pass(self, iterations: int = 5) -> bool:
        """
        Runs random import order fuzzing passes.
        """
        top_mod = importlib.import_module(self.package_name)
        submods = [m for m in sys.modules.keys() if m.startswith(self.package_name + ".")]

        baseline_snap = OECSnapshotEngine.capture([self.package_name])

        for i in range(iterations):
            shuffled_mods = list(submods)
            random.shuffle(shuffled_mods)

            for mname in shuffled_mods:
                mod = sys.modules.get(mname)
                if mod is not None:
                    attrs = list(dir(mod))
                    random.shuffle(attrs)
                    for attr in attrs[:10]:
                        try:
                            getattr(mod, attr)
                        except Exception:
                            pass

            pass_snap = OECSnapshotEngine.capture([self.package_name])
            diff = baseline_snap.diff(pass_snap)
            if diff:
                return False
        return True
