"""
Verification & Benchmark Program for Selective on an AI & NLP Stack.
Stack Libraries: nltk, spacy, sklearn, torch, transformers.

Objective:
Demonstrates and measures baseline vs Selective demand-loading performance,
peak RSS memory usage, module load counts, speedup percentages, and verifies
Observable Equivalence (OEC) contract outputs.
"""

import sys
import os
import json
import time
import resource
import statistics
import subprocess
from pathlib import Path

PYTHON_EXE = sys.executable
PACKAGES = ["nltk", "spacy", "sklearn", "torch", "transformers"]

WORKLOAD_CODE = """
import sys
import json
import time
import resource

def run_ai_pipeline():
    t_start = time.perf_counter()
    import nltk
    import spacy
    import sklearn
    import torch
    import transformers
    t_imported = time.perf_counter()
    import_modules_count = len(sys.modules)

    # 1. NLTK Text Processing & Stemming
    from nltk.stem import PorterStemmer
    from nltk.tokenize import RegexpTokenizer
    tokenizer = RegexpTokenizer(r'\\w+')
    stemmer = PorterStemmer()
    tokens = [stemmer.stem(t) for t in tokenizer.tokenize("Selective demand loader optimizes Python startup time across AI libraries")]

    # 2. SpaCy NLP Pipeline Container Initialization
    nlp = spacy.blank("en")
    doc = nlp("Selective demand loader optimizes Python startup time across AI libraries")

    # 3. Scikit-Learn TF-IDF Feature Matrix Extraction
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(["Selective demand loader", "optimizes Python startup time across AI libraries"])

    # 4. PyTorch Tensor Neural Layer Forward Calculation
    import torch.nn as nn
    tensor_x = torch.tensor(X.toarray(), dtype=torch.float32)
    linear = nn.Linear(X.shape[1], 2)
    out = linear(tensor_x)

    # 5. HuggingFace Transformers Configuration Parsing
    from transformers import AutoConfig
    config = AutoConfig.for_model("bert")
    t_end = time.perf_counter()

    return {
        "tokens_count": len(tokens),
        "spacy_doc_len": len(doc),
        "tfidf_shape": list(X.shape),
        "tensor_output_shape": list(out.shape),
        "transformers_model_type": config.model_type,
        "import_modules_loaded": import_modules_count,
        "total_modules_loaded": len(sys.modules),
        "import_ms": (t_imported - t_start) * 1000.0,
        "total_pipeline_ms": (t_end - t_start) * 1000.0,
        "rss_self_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
    }

if __name__ == "__main__":
    res = run_ai_pipeline()
    print("---PIPELINE_RESULT_BEGIN---")
    print(json.dumps(res))
    print("---PIPELINE_RESULT_END---")
"""

def run_subprocess_measurement(enable_selective: bool, runs: int = 3):
    durations = []
    rss_list = []
    pipeline_result = None

    env = dict(os.environ)
    if not enable_selective:
        env["SELECTIVE_DISABLE"] = "1"
    else:
        env.pop("SELECTIVE_DISABLE", None)

    if enable_selective:
        cmd = [
            PYTHON_EXE, "-c",
            "from selective.deploy.cache_resolver import CacheResolver\n"
            "from selective.analyzer.serializer import GraphSerializer\n"
            "from selective.loader.finder import SelectiveFinder\n"
            "cache_dir, _ = CacheResolver.resolve_cache_dir()\n"
            "for pkg in ['nltk', 'spacy', 'sklearn', 'torch', 'transformers']:\n"
            "    gp = cache_dir / f'{pkg}_graph.json'\n"
            "    if gp.exists():\n"
            "        g = GraphSerializer.load_json(gp)\n"
            "        SelectiveFinder.register_package(pkg, g)\n"
            "SelectiveFinder.install()\n" + WORKLOAD_CODE
        ]
    else:
        cmd = [PYTHON_EXE, "-c", WORKLOAD_CODE]

    # Warmup run
    warmup_res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if warmup_res.returncode != 0:
        print(f"Warmup Subprocess Error (Selective={enable_selective}): Exit Code {warmup_res.returncode}", file=sys.stderr)
        print("STDERR:\n" + warmup_res.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"Workload subprocess crashed during warmup (Selective={enable_selective})")

    for _ in range(runs):
        t0 = time.perf_counter()
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        t1 = time.perf_counter()

        if res.returncode != 0:
            print(f"Subprocess Error (Selective={enable_selective}): Exit Code {res.returncode}", file=sys.stderr)
            print("STDERR:\n" + res.stderr[-2000:], file=sys.stderr)
            raise RuntimeError(f"Workload subprocess crashed (Selective={enable_selective})")

        durations.append(t1 - t0)

        if "---PIPELINE_RESULT_BEGIN---" in res.stdout:
            try:
                raw_json = res.stdout.split("---PIPELINE_RESULT_BEGIN---")[1].split("---PIPELINE_RESULT_END---")[0].strip()
                pipeline_result = json.loads(raw_json)
                if "rss_self_mb" in pipeline_result:
                    rss_list.append(pipeline_result["rss_self_mb"])
            except Exception as je:
                print(f"JSON Parse Error: {je}\nSTDOUT:\n{res.stdout}", file=sys.stderr)

    return {
        "median_sec": statistics.median(durations),
        "mean_sec": statistics.mean(durations),
        "min_sec": min(durations),
        "max_sec": max(durations),
        "stdev_sec": statistics.stdev(durations) if len(durations) > 1 else 0.0,
        "max_rss_mb": max(rss_list) if rss_list else 0.0,
        "result": pipeline_result,
    }

def run_benchmark_verification():
    print("=" * 80)
    print("Selective AI Stack Benchmark & Equivalence Verification")
    print("Stack: nltk, spacy, sklearn, torch, transformers")
    print("=" * 80)

    # 1. Pre-scan packages to build graphs in cache
    print("\n[1/3] Pre-scanning AI stack packages...")
    from selective.deploy.cache_resolver import CacheResolver
    from selective.cli.commands import _scan_single_package

    cache_dir, _ = CacheResolver.resolve_cache_dir()
    for pkg in PACKAGES:
        gp = cache_dir / f"{pkg}_graph.json"
        if not gp.exists():
            print(f"  Scanning package '{pkg}'...")
            try:
                _scan_single_package(pkg, cache_dir)
            except Exception as e:
                print(f"  Warning scanning {pkg}: {e}")

    # 2. Run Baseline (Eager Python)
    print("\n[2/3] Measuring Baseline Eager Import Execution (SELECTIVE_DISABLE=1)...")
    baseline = run_subprocess_measurement(enable_selective=False, runs=3)
    baseline_med_ms = baseline["median_sec"] * 1000.0

    # 3. Run Selective (Demand-Loaded)
    print("\n[3/3] Measuring Selective Demand-Loaded Execution...")
    selective = run_subprocess_measurement(enable_selective=True, runs=3)
    selective_med_ms = selective["median_sec"] * 1000.0

    # Speedup Calculation
    speedup_pct = (baseline["median_sec"] - selective["median_sec"]) / baseline["median_sec"] * 100.0
    saved_ms = baseline_med_ms - selective_med_ms

    # Equivalence Contract Verification
    base_res = baseline["result"] or {}
    sel_res = selective["result"] or {}
    oec_passed = (
        base_res.get("tokens_count") == sel_res.get("tokens_count") and
        base_res.get("spacy_doc_len") == sel_res.get("spacy_doc_len") and
        base_res.get("tfidf_shape") == sel_res.get("tfidf_shape") and
        base_res.get("tensor_output_shape") == sel_res.get("tensor_output_shape") and
        base_res.get("transformers_model_type") == sel_res.get("transformers_model_type")
    )

    base_imp_ms = base_res.get("import_ms", 0.0)
    sel_imp_ms = sel_res.get("import_ms", 0.0)
    imp_speedup = (base_imp_ms - sel_imp_ms) / base_imp_ms * 100.0 if base_imp_ms > 0 else 0.0

    summary = {
        "workload": "AI Stack Text Feature Pipeline (nltk + spacy + sklearn + torch + transformers)",
        "baseline_import_ms": round(base_imp_ms, 2),
        "selective_import_ms": round(sel_imp_ms, 2),
        "import_speedup_pct": round(imp_speedup, 2),
        "baseline_import_modules": base_res.get("import_modules_loaded", 0),
        "selective_import_modules": sel_res.get("import_modules_loaded", 0),
        "baseline_total_ms": round(baseline_med_ms, 2),
        "selective_total_ms": round(selective_med_ms, 2),
        "total_saved_ms": round(saved_ms, 2),
        "total_speedup_pct": round(speedup_pct, 2),
        "baseline_rss_mb": round(baseline["max_rss_mb"], 2),
        "selective_rss_mb": round(selective["max_rss_mb"], 2),
        "baseline_modules_loaded": base_res.get("total_modules_loaded", 0),
        "selective_modules_loaded": sel_res.get("total_modules_loaded", 0),
        "oec_observable_equivalence_passed": oec_passed,
    }

    out_file = Path(__file__).parent / "ai_stack_benchmark_results.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 80)
    print("BENCHMARK & VERIFICATION RESULTS")
    print("=" * 80)
    print(f"Workload:                     {summary['workload']}")
    print(f"Observable Equivalence (OEC): {'PASSED (Zero Diffs)' if oec_passed else 'FAILED'}")
    print("-" * 80)
    print("IMPORT / STARTUP PHASE LATENCY (Time to First Code):")
    print(f"  Baseline Import Time      : {summary['baseline_import_ms']} ms ({summary['baseline_import_modules']} modules loaded)")
    print(f"  Selective Import Time     : {summary['selective_import_ms']} ms ({summary['selective_import_modules']} modules loaded)")
    print(f"  Startup Speedup           : {summary['import_speedup_pct']} %")
    print("-" * 80)
    print("FULL WORKLOAD PIPELINE EXECUTION (End-to-End Execution):")
    print(f"  Baseline Total Time       : {summary['baseline_total_ms']} ms ({summary['baseline_modules_loaded']} modules loaded)")
    print(f"  Selective Total Time      : {summary['selective_total_ms']} ms ({summary['selective_modules_loaded']} modules loaded)")
    print(f"  Total Workload Speedup    : {summary['total_speedup_pct']} %")
    print("=" * 80)

    return summary

def test_ai_stack_benchmark():
    summary = run_benchmark_verification()
    assert summary["oec_observable_equivalence_passed"] is True, "Observable Equivalence check failed!"
    assert summary["import_speedup_pct"] > 0, f"Expected positive startup speedup, got {summary['import_speedup_pct']}%"

if __name__ == "__main__":
    run_benchmark_verification()
