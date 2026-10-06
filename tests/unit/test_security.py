"""
Unit tests for Supply-Chain Security Analyzer, Genome, and Diff Engine.
"""

import tempfile
import json
from pathlib import Path
from selective.analyzer.security import SecurityAnalyzer, SecurityASTVisitor, SupplyChainDiff, BehavioralGenome
import ast

def test_security_ast_visitor_detections():
    source = """
import os
import sys
import subprocess
import socket

eval("1 + 1")
exec("import math")
subprocess.run(["ls"])
s = socket.socket()
os.environ["SECRET"] = "123"
sys.addaudithook(lambda event, args: None)
"""
    tree = ast.parse(source)
    visitor = SecurityASTVisitor("test.module")
    visitor.visit(tree)

    categories = [f.category for f in visitor.findings]
    assert "Dynamic execution" in categories
    assert "Process execution" in categories
    assert "Network capability" in categories
    assert "Environment mutation" in categories
    assert "Import hooks" in categories

def test_behavioral_genome_id_stability():
    genome1 = BehavioralGenome("dummy", "1.0", ["m1"], 5, ["lib.so"], 1, 0, 1, 0, [])
    genome2 = BehavioralGenome("dummy", "1.0", ["m1"], 5, ["lib.so"], 1, 0, 1, 0, [])
    
    assert genome1.genome_id == genome2.genome_id
    assert genome1.genome_id.startswith("sha256:")

def test_supply_chain_diff():
    old_report = {
        "package_name": "dummy",
        "genome_id": "sha256:1111",
        "overall_severity": "LOW",
        "findings": [{"module": "m1", "pattern": "open()", "severity": "LOW"}]
    }
    new_report = {
        "package_name": "dummy",
        "genome_id": "sha256:2222",
        "overall_severity": "HIGH",
        "findings": [
            {"module": "m1", "pattern": "open()", "severity": "LOW"},
            {"module": "m2", "pattern": "eval()", "severity": "HIGH"}
        ]
    }

    diff = SupplyChainDiff.diff_reports(old_report, new_report)
    assert diff["risk_increased"] is True
    assert diff["added_findings_count"] == 1
    assert diff["old_overall_severity"] == "LOW"
    assert diff["new_overall_severity"] == "HIGH"
