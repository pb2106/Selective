"""
Differential Verification Engine (`selective verify`).
Runs script under normal Python vs Selective optimization, compares OEC snapshots, and reports diffs.
"""

import sys
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from selective.harness.oec import OECSnapshot

PYTHON_EXE = sys.executable

RUN_HARNESS_WRAPPER = """
import sys
import json
import importlib
from selective.harness.oec import OECSnapshotEngine

managed_pkg = "{package_name}"
script_path = "{script_path}"

# Force resolve all managed modules at end if Selective is enabled
def force_resolve_all(pkg):
    mods = [m for m in list(sys.modules.keys()) if m == pkg or m.startswith(pkg + ".")]
    for mname in mods:
        mod = sys.modules.get(mname)
        if mod is not None:
            for attr in dir(mod):
                try:
                    getattr(mod, attr)
                except Exception:
                    pass

# Execute user script
with open(script_path, "r") as f:
    code = f.read()

exec(compile(code, script_path, "exec"))

if managed_pkg:
    force_resolve_all(managed_pkg)

snap = OECSnapshotEngine.capture([managed_pkg] if managed_pkg else [])
print("---OEC_SNAPSHOT_BEGIN---")
print(json.dumps(snap.to_dict()))
print("---OEC_SNAPSHOT_END---")
"""

class DifferentialVerifier:
    def __init__(self, script_path: str, package_name: str = ""):
        self.script_path = Path(script_path).resolve()
        self.package_name = package_name

    def _run_subprocess(self, enable_selective: bool = False) -> Tuple[int, str, Optional[OECSnapshot]]:
        wrapper_code = RUN_HARNESS_WRAPPER.format(
            package_name=self.package_name,
            script_path=str(self.script_path)
        )
        
        env = dict(sys.environ)
        if not enable_selective:
            env["SELECTIVE_DISABLE"] = "1"
        else:
            env.pop("SELECTIVE_DISABLE", None)

        cmd = [PYTHON_EXE, "-c", wrapper_code]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)

        snapshot = None
        if "---OEC_SNAPSHOT_BEGIN---" in res.stdout:
            try:
                raw_json = res.stdout.split("---OEC_SNAPSHOT_BEGIN---")[1].split("---OEC_SNAPSHOT_END---")[0].strip()
                data = json.loads(raw_json)
                snapshot = OECSnapshot(
                    data["L1_Namespace"],
                    data["L2_Registries"],
                    data["L3_Behavior"],
                    data["L4_ProcessState"],
                    data["L5_ErrorTiming"]
                )
            except Exception:
                pass

        return res.returncode, res.stdout + res.stderr, snapshot

    def verify(self) -> Dict[str, Any]:
        ret_a, out_a, snap_a = self._run_subprocess(enable_selective=False)
        ret_b, out_b, snap_b = self._run_subprocess(enable_selective=True)

        if snap_a is None or snap_b is None:
            return {
                "passed": False,
                "error": "Failed to capture OEC snapshots",
                "baseline_output": out_a,
                "target_output": out_b,
                "diffs": {}
            }

        diffs = snap_a.diff(snap_b)
        passed = (len(diffs) == 0) and (ret_a == ret_b)

        return {
            "passed": passed,
            "baseline_exit_code": ret_a,
            "target_exit_code": ret_b,
            "diffs": diffs,
            "baseline_output": out_a,
            "target_output": out_b,
        }
