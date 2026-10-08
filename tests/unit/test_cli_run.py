"""
Regression tests for `selective run`.

The benchmark suite once timed `selective run -c CODE` while `run` had no `-c`
option: argparse exited immediately and the crash was recorded as a ~95% speedup.
"""

import subprocess
import sys


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "selective.cli.main", "run", *args],
        capture_output=True,
        text=True,
    )


def test_run_dash_c_executes_code():
    res = _run_cli("-c", "import sys; print('ok', sys.argv[0])")
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "ok -c"


def test_run_dash_c_propagates_failure():
    res = _run_cli("-c", "raise SystemExit(3)")
    assert res.returncode == 3


def test_run_missing_script_fails():
    res = _run_cli("definitely_missing_script_xyz.py")
    assert res.returncode != 0
