"""
Unit tests for NativeScanner and SafetyClassifier.
"""

from pathlib import Path
from selective.analyzer.scanner import ModuleFileInfo
from selective.analyzer.import_extractor import ImportRecord
from selective.analyzer.side_effects import SideEffectRecord, SideEffectAnalyzer
from selective.analyzer.native_scanner import NativeScanner
from selective.analyzer.classifier import SafetyClassifier

def test_safety_classifier_pure_module():
    info = ModuleFileInfo("pkg.pure", Path("/path/pure.py"), "pure.py", "hash1", False, False)
    imports = [ImportRecord("import", "os", [("os", None)], 1, "module")]
    side_effects = []

    classifier = SafetyClassifier()
    cls = classifier.classify_module(info, imports, side_effects)

    assert cls.safety_class == "SAFE_LAZY"
    assert cls.evidence_tier == 2

def test_safety_classifier_side_effect_module():
    info = ModuleFileInfo("pkg.side", Path("/path/side.py"), "side.py", "hash2", False, False)
    imports = []
    side_effects = [SideEffectRecord("REGISTRATION_CALL", "Register op", 5, None)]

    classifier = SafetyClassifier()
    cls = classifier.classify_module(info, imports, side_effects)

    assert cls.safety_class == "EAGER_REQUIRED"
    assert cls.evidence_tier == 4

def test_safety_classifier_extension_module():
    info = ModuleFileInfo("pkg._C", Path("/path/_C.so"), "_C.so", "hash3", False, True)
    classifier = SafetyClassifier()
    cls = classifier.classify_module(info, [], [])

    assert cls.safety_class == "NATIVE_REQUIRED"
    assert cls.evidence_tier == 4
