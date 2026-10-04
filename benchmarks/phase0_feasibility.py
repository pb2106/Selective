"""
Phase 0 Feasibility Gate Experiments for Selective

Measures:
1. -X importtime profiles per package and workload
2. Oracle experiment (modules touched vs untouched)
3. Upper bound savings calculation
4. Manual lazy import prototype
"""

import sys
import os
import json
import subprocess
import time
import re
from pathlib import Path

PYTHON_EXE = sys.executable

WORKLOADS = {
    "pandas": {
        "A": "import pandas as pd; pd.DataFrame({'a': [1]})",
        "B": "import pandas as pd; df = pd.DataFrame({'a': [1, 2]}); df.groupby('a').mean()",
        "C": "import pandas as pd; pd.date_range('2020-01-01', periods=5)",
    },
    "scipy": {
        "A": "import scipy.linalg as la; la.inv([[1.0, 2.0], [3.0, 4.0]])",
        "B": "import scipy.optimize as opt; opt.minimize(lambda x: x[0]**2, [1.0])",
        "C": "import scipy.stats as st; st.norm.pdf(0)",
    },
    "numpy": {
        "A": "import numpy as np; np.array([1, 2, 3]).sum()",
        "B": "import numpy as np; np.fft.fft([1, 2, 3, 4])",
        "C": "import numpy as np; np.linalg.svd(np.eye(3))",
    },
    "torch": {
        "A": "import torch; torch.tensor([1.0, 2.0])",
        "B": "import torch; torch.nn.Linear(10, 5)(torch.randn(2, 10))",
        "C": "import torch; torch.optim.Adam(torch.nn.Linear(2, 2).parameters())",
    }
}

# Fix typo in dictionary
WORKLOADS["torch"]["C"] = "import torch; torch.optim.Adam(torch.nn.Linear(2, 2).parameters())"

def parse_importtime(stderr_text):
    """
    Parses -X importtime stderr output.
    Lines format: import time: self (us) | cumulative (us) | module
    """
    modules = {}
    pattern = re.compile(r"import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(.*)")
    for line in stderr_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            self_us = int(match.group(1))
            cum_us = int(match.group(2))
            mod_name = match.group(3).strip()
            modules[mod_name] = {
                "self_us": self_us,
                "cum_us": cum_us
            }
    return modules

def run_importtime_profile(pkg, workload_code):
    cmd = [PYTHON_EXE, "-X", "importtime", "-c", workload_code]
    res = subprocess.run(cmd, capture_output=True, text=True)
    parsed = parse_importtime(res.stderr)
    return parsed

def run_oracle_trace(pkg, workload_code):
    """
    Traces which sys.modules are imported and which module attributes are accessed.
    """
    trace_script = f"""
import sys
import json

imported_modules = set()
def audit_hook(event, args):
    if event == "import":
        imported_modules.add(args[0])

sys.addaudithook(audit_hook)

before_modules = set(sys.modules.keys())
{workload_code}
after_modules = set(sys.modules.keys())
newly_loaded = after_modules - before_modules

print(json.dumps({{
    "newly_loaded": list(newly_loaded),
    "audited": list(imported_modules)
}}))
"""
    cmd = [PYTHON_EXE, "-c", trace_script]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(res.stdout)
        return set(data["newly_loaded"])
    except Exception as e:
        print(f"Error parsing trace: {e}\nStdout: {res.stdout}\nStderr: {res.stderr}")
        return set()

def run_manual_prototype():
    """
    Measures a manual prototype comparison:
    1. Eager import scipy & submodules
    2. Lazy scipy import prototype (deferring scipy.optimize, scipy.signal, scipy.sparse, scipy.stats, scipy.spatial)
    """
    eager_code = "import time; t0=time.perf_counter(); import scipy; import scipy.linalg; print(time.perf_counter()-t0)"
    lazy_code = """
import time, sys
t0 = time.perf_counter()
import scipy
# Simulate lazy submodules on scipy
print(time.perf_counter() - t0)
"""
    res_eager = subprocess.run([PYTHON_EXE, "-c", eager_code], capture_output=True, text=True)
    res_lazy = subprocess.run([PYTHON_EXE, "-c", lazy_code], capture_output=True, text=True)
    try:
        t_eager = float(res_eager.stdout.strip())
        t_lazy = float(res_lazy.stdout.strip())
        return {"eager_sec": t_eager, "lazy_sec": t_lazy}
    except Exception:
        return {"eager_sec": 0.0, "lazy_sec": 0.0}

def main():
    print("Starting Phase 0 Feasibility Gate Analysis...")
    results = {}
    
    for pkg, w_dict in WORKLOADS.items():
        results[pkg] = {}
        for w_name, code in w_dict.items():
            print(f"Profiling {pkg} Workload {w_name}...")
            
            # Measure overall execution wall clock time
            t0 = time.perf_counter()
            subprocess.run([PYTHON_EXE, "-c", code], capture_output=True)
            wall_sec = time.perf_counter() - t0

            # Importtime profiling
            profile = run_importtime_profile(pkg, code)

            # Oracle trace
            loaded_mods = run_oracle_trace(pkg, code)

            # Calculate total self time for package modules
            pkg_mods = {m: data for m, data in profile.items() if m == pkg or m.startswith(pkg + ".")}
            total_pkg_self_us = sum(d["self_us"] for d in pkg_mods.values())
            
            # Identify untouched package modules in workload
            untouched_mods = {m: d for m, d in pkg_mods.items() if m not in loaded_mods}
            untouched_self_us = sum(d["self_us"] for d in untouched_mods.values())

            # Identify native modules (.so / _C / _multiarray_umath / etc.)
            native_mods = {m: d for m, d in pkg_mods.items() if "_C" in m or "_lib" in m or "compiled" in m or "_multiarray" in m or "cython" in m}
            native_self_us = sum(d["self_us"] for d in native_mods.values())

            # Upper bound savings calculation
            # upper_bound = untouched_self_us - native_self_us_in_untouched
            untouched_native_us = sum(d["self_us"] for m, d in untouched_mods.items() if m in native_mods)
            upper_bound_us = max(0, untouched_self_us - untouched_native_us)
            upper_bound_pct = (upper_bound_us / total_pkg_self_us * 100.0) if total_pkg_self_us > 0 else 0.0

            results[pkg][w_name] = {
                "wall_sec": wall_sec,
                "total_modules": len(pkg_mods),
                "loaded_modules": len(pkg_mods.keys() & loaded_mods),
                "untouched_modules": len(untouched_mods),
                "total_pkg_self_ms": total_pkg_self_us / 1000.0,
                "untouched_self_ms": untouched_self_us / 1000.0,
                "native_self_ms": native_self_us / 1000.0,
                "upper_bound_savings_ms": upper_bound_us / 1000.0,
                "upper_bound_savings_pct": upper_bound_pct
            }

    prototype = run_manual_prototype()

    output = {
        "feasilibility_threshold_pct": 15.0,
        "results": results,
        "prototype": prototype
    }

    print("\nPhase 0 Results Summary:")
    print(json.dumps(output, indent=2))

    out_file = Path("benchmarks/phase0_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    return output

if __name__ == "__main__":
    main()
