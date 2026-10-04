"""
Unit tests for StaticPruner.
"""

from selective.analyzer.import_extractor import ImportRecord
from selective.analyzer.static_pruner import StaticPruner

def test_static_pruner_type_checking():
    pruner = StaticPruner()
    rec_normal = ImportRecord("import", "os", [("os", None)], 1, "module")
    rec_tc = ImportRecord("import", "typing_extensions", [("typing_extensions", None)], 2, "module", is_type_checking=True)

    kept, elim = pruner.prune_imports([rec_normal, rec_tc])

    assert len(kept) == 1
    assert kept[0].target_module == "os"
    assert len(elim) == 1
    assert elim[0][0].target_module == "typing_extensions"
    assert elim[0][1] == "TYPE_CHECKING block"
