"""
Unit tests for ProjectScanner and project directory scanning.
"""

import tempfile
from pathlib import Path
from selective.analyzer.scanner import ProjectScanner
from selective.cli.commands import cmd_scan

def test_project_scanner_discovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "my_project"
        proj_dir.mkdir()
        
        # Write project python files importing numpy, pandas, scipy, torch, math, os
        (proj_dir / "app.py").write_text("import numpy as np\nimport math\nfrom scipy import linalg\n", encoding="utf-8")
        
        sub_dir = proj_dir / "services"
        sub_dir.mkdir()
        (sub_dir / "model.py").write_text("import torch\nimport pandas as pd\nfrom . import utils\n", encoding="utf-8")
        (sub_dir / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")

        scanner = ProjectScanner(str(proj_dir))
        deps = scanner.discover_third_party_dependencies()

        assert "numpy" in deps
        assert "scipy" in deps
        assert "torch" in deps
        assert "pandas" in deps
        assert "math" not in deps
        assert "services" not in deps

def test_cmd_scan_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "sample_app"
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("import numpy as np\nimport scipy\n", encoding="utf-8")

        ret = cmd_scan(str(proj_dir), is_project=True, json_out=True)
        assert ret == 0
