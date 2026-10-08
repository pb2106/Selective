"""
Automated Benchmark Suite Runner for Selective.
Measures baseline vs Selective wall-clock time, per-process peak RSS, module counts,
and finder microbenchmark overhead, and writes raw results to JSON.

Correctness rules:
- Any subprocess that exits non-zero aborts the benchmark (a crash is never timed).
- Peak RSS is reported by each child itself via RUSAGE_SELF (RUSAGE_CHILDREN is a
  cumulative maximum across all children and cannot compare two modes).
- One untimed warm-up run per mode, so bytecode-cache creation is not measured.
"""

import sys
import os
import json
import time
import subprocess
import statistics
from pathlib import Path

PYTHON_EXE = sys.executable
RESULTS_FILE = Path(__file__).resolve().parent / "results_final.json"
METRICS_MARKER = "__SELECTIVE_BENCH_METRICS__="

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

# Appended to every workload: the child reports its own peak RSS and module count.
METRICS_SUFFIX = (
    "\nimport sys as _bs, resource as _br, json as _bj\n"
    "_bs.stderr.write('" + METRICS_MARKER + "' + _bj.dumps({"
    "'rss_mb': _br.getrusage(_br.RUSAGE_SELF).ru_maxrss / 1024.0, "
    "'modules': len(_bs.modules)}) + '\\n')\n"
)


class BenchmarkError(RuntimeError):
    pass


def _parse_metrics(stderr: str) -> dict:
    for line in reversed(stderr.splitlines()):
        if line.startswith(METRICS_MARKER):
            return json.loads(line[len(METRICS_MARKER):])
    raise BenchmarkError("Workload finished without reporting metrics (did it run at all?)")


def _run_once(cmd, env):
    t0 = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    t1 = time.perf_counter()
    if res.returncode != 0:
        raise BenchmarkError(
            f"Command failed with exit code {res.returncode}: {' '.join(cmd[:4])} ...\n"
            f"--- stderr (tail) ---\n{res.stderr[-3000:]}"
        )
    return t1 - t0, _parse_metrics(res.stderr)


def measure_execution(cmd, env, runs=3):
    _run_once(cmd, env)  # warm-up, untimed

    durations, rss, modules = [], [], []
    for _ in range(runs):
        dt, metrics = _run_once(cmd, env)
        durations.append(dt)
        rss.append(metrics["rss_mb"])
        modules.append(metrics["modules"])

    return {
        "median_sec": statistics.median(durations),
        "mean_sec": statistics.mean(durations),
        "min_sec": min(durations),
        "max_sec": max(durations),
        "stdev_sec": statistics.stdev(durations) if len(durations) > 1 else 0.0,
        "max_rss_mb": max(rss),
        "modules_loaded": statistics.median(modules),
    }


def ensure_graphs(packages):
    """Scan packages that have no cached graph, so `selective run` actually manages them."""
    from selective.deploy.cache_resolver import CacheResolver
    from selective.cli.commands import _scan_single_package

    cache_dir, _ = CacheResolver.resolve_cache_dir()
    for pkg in packages:
        if not (cache_dir / f"{pkg}_graph.json").exists():
            print(f"  Scanning package '{pkg}'...")
            _scan_single_package(pkg, cache_dir)


def measure_microbenchmark_overhead():
    code = """
import json
import time
from selective.loader.finder import SelectiveFinder

finder = SelectiveFinder()
SelectiveFinder.register_package("managed_dummy")

t0 = time.perf_counter_ns()
for _ in range(10000):
    finder.find_spec("sys", None)
t1 = time.perf_counter_ns()

print(json.dumps({"unmanaged_overhead_us": (t1 - t0) / 10000.0 / 1000.0}))
"""
    res = subprocess.run([PYTHON_EXE, "-c", code], capture_output=True, text=True)
    if res.returncode != 0:
        raise BenchmarkError(f"Microbenchmark failed:\n{res.stderr[-3000:]}")
    return json.loads(res.stdout)["unmanaged_overhead_us"]


def main():
    print("Executing Selective Automated Benchmark Suite...")

    print("Ensuring package graphs exist...")
    ensure_graphs(list(WORKLOADS.keys()))

    micro_us = measure_microbenchmark_overhead()
    print(f"Finder microbenchmark unmanaged import overhead: {micro_us:.3f} microseconds")

    env_baseline = dict(os.environ, SELECTIVE_DISABLE="1")
    env_selective = {k: v for k, v in os.environ.items() if k != "SELECTIVE_DISABLE"}

    benchmark_data = {}
    for pkg, w_dict in WORKLOADS.items():
        benchmark_data[pkg] = {}
        for w_name, code in w_dict.items():
            print(f"Benchmarking {pkg} Workload {w_name}...")
            full_code = code + METRICS_SUFFIX

            cmd_baseline = [PYTHON_EXE, "-c", full_code]
            cmd_selective = [PYTHON_EXE, "-m", "selective.cli.main", "run", "-c", full_code]

            metrics_baseline = measure_execution(cmd_baseline, env_baseline, runs=3)
            metrics_selective = measure_execution(cmd_selective, env_selective, runs=3)

            speedup_pct = (metrics_baseline["median_sec"] - metrics_selective["median_sec"]) / metrics_baseline["median_sec"] * 100.0
            print(f"  baseline {metrics_baseline['median_sec']:.3f}s ({metrics_baseline['modules_loaded']:.0f} modules) | "
                  f"selective {metrics_selective['median_sec']:.3f}s ({metrics_selective['modules_loaded']:.0f} modules) | "
                  f"speedup {speedup_pct:+.1f}%")

            benchmark_data[pkg][w_name] = {
                "baseline": metrics_baseline,
                "selective": metrics_selective,
                "speedup_pct": speedup_pct,
            }

    output = {
        "python": sys.version.split()[0],
        "microbenchmark_unmanaged_us": micro_us,
        "results": benchmark_data,
    }

    RESULTS_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nBenchmark Suite Completed. Results written to {RESULTS_FILE}")
    return output


if __name__ == "__main__":
    try:
        main()
    except BenchmarkError as e:
        print(f"\n[BENCHMARK ABORTED] {e}", file=sys.stderr)
        sys.exit(1)
