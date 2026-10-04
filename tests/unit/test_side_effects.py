"""
Unit tests for SideEffectAnalyzer.
"""

import ast
from selective.analyzer.side_effects import SideEffectAnalyzer

def test_side_effect_analyzer_registration():
    source = """
import atexit
import logging

logging.basicConfig(level=logging.INFO)

def my_exit(): pass
atexit.register(my_exit)

def register_custom_op(): pass
register_custom_op()
"""
    tree = ast.parse(source)
    analyzer = SideEffectAnalyzer()
    effects = analyzer.analyze(tree)

    categories = [e.category for e in effects]
    assert "LOGGING_WARNING_CONFIG" in categories
    assert "SYSTEM_HOOK" in categories
    assert "REGISTRATION_CALL" in categories
