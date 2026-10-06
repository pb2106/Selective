"""
Unit tests for SelectiveArtifactBuilder (Container and Serverless optimization).
"""

import tempfile
import json
from pathlib import Path
from selective.deploy.builder import SelectiveArtifactBuilder

def test_builder_container_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "app"
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("import numpy as np\nimport math\n", encoding="utf-8")

        bake_dir = Path(tmpdir) / "baked_cache"

        builder = SelectiveArtifactBuilder(str(proj_dir), build_type="container", bake_dir=str(bake_dir))
        manifest = builder.build()

        assert manifest["build_type"] == "container"
        assert "python_version" in manifest
        assert manifest["performance_metrics"]["metric_type"] == "estimated"
        assert (bake_dir / "build_manifest.json").exists()

def test_builder_lambda_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "lambda_fn"
        proj_dir.mkdir()
        (proj_dir / "lambda_function.py").write_text("import math\n", encoding="utf-8")

        builder = SelectiveArtifactBuilder(str(proj_dir), build_type="lambda")
        manifest = builder.build()

        assert manifest["build_type"] == "lambda"
        assert "reproducibility" in manifest
