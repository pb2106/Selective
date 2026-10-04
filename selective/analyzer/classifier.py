"""
Safety Classifier for Selective.
Classifies import edges and module loading safety into evidence tiers and safety classes.
"""

from typing import List, Tuple, Dict, Any
from selective.analyzer.import_extractor import ImportRecord
from selective.analyzer.side_effects import SideEffectRecord
from selective.analyzer.scanner import ModuleFileInfo

class SafetyClassification:
    def __init__(self, safety_class: str, evidence_tier: int, reason: str):
        self.safety_class = safety_class
        self.evidence_tier = evidence_tier
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "safety_class": self.safety_class,
            "evidence_tier": self.evidence_tier,
            "reason": self.reason,
        }

class SafetyClassifier:
    def classify_module(
        self,
        module_info: ModuleFileInfo,
        imports: List[ImportRecord],
        side_effects: List[SideEffectRecord],
        mode: str = "conservative"
    ) -> SafetyClassification:
        """
        Classifies module import safety.
        Modes: 'conservative' (default), 'balanced', 'aggressive'.
        """
        # 1. Native extension modules
        if module_info.is_extension:
            return SafetyClassification(
                safety_class="NATIVE_REQUIRED",
                evidence_tier=4,
                reason="Native compiled extension (.so/.pyd/.dylib)"
            )

        # 2. Syntax or parse errors
        if module_info.error:
            return SafetyClassification(
                safety_class="EAGER_REQUIRED",
                evidence_tier=4,
                reason=f"Module parse error: {module_info.error}"
            )

        # 3. Security configurations
        for se in side_effects:
            if se.category in ("SECURITY_CONFIG", "SYS_MODULES_MUTATION"):
                return SafetyClassification(
                    safety_class="SECURITY_EAGER",
                    evidence_tier=4,
                    reason=f"Security configuration or sys.modules mutation: {se.description}"
                )

        # 4. Eager required side effects
        for se in side_effects:
            if se.category in ("REGISTRATION_CALL", "REGISTRATION_DECORATOR", "SYSTEM_HOOK", "PLUGIN_ENUMERATION", "ENV_WRITE"):
                return SafetyClassification(
                    safety_class="EAGER_REQUIRED",
                    evidence_tier=4,
                    reason=f"Module-level side effect: {se.description}"
                )

        # 5. Check imports
        for imp in imports:
            if imp.statement_type == "star_import":
                return SafetyClassification(
                    safety_class="EAGER_REQUIRED",
                    evidence_tier=4,
                    reason="Star import (from ... import *) cannot be lazy"
                )

        # 6. Pure module body (Tier 1 / Tier 2)
        if len(side_effects) == 0:
            return SafetyClassification(
                safety_class="SAFE_LAZY",
                evidence_tier=1 if len(imports) == 0 else 2,
                reason="Pure module body containing only defs, classes, and safe imports"
            )

        # Default fallback
        if mode == "aggressive":
            return SafetyClassification(
                safety_class="SAFE_LAZY",
                evidence_tier=3,
                reason="Aggressive policy classification"
            )
        else:
            return SafetyClassification(
                safety_class="UNKNOWN",
                evidence_tier=3,
                reason="Unproven dynamic safety; default eager under conservative policy"
            )
