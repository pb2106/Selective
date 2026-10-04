"""
Monotonic Edge Bisection Engine (`selective bisect`).
Isolates minimal lazy edges causing OEC verification diffs and pins them EAGER_REQUIRED.
"""

from typing import List, Dict, Any, Tuple
from selective.analyzer.graph_builder import PackageGraph, GraphEdge

class EdgeBisector:
    def __init__(self, graph: PackageGraph, verify_fn):
        self.graph = graph
        self.verify_fn = verify_fn

    def bisect(self) -> Tuple[List[GraphEdge], List[GraphEdge]]:
        """
        Bisects lazy edges in the graph to find the minimal set causing a verification diff.
        Returns (problematic_edges, safe_edges).
        """
        lazy_edges = [e for e in self.graph.edges if e.safety_class == "SAFE_LAZY"]
        if not lazy_edges:
            return [], []

        problematic: List[GraphEdge] = []
        candidates = list(lazy_edges)

        while len(candidates) > 0:
            mid = len(candidates) // 2
            test_subset = candidates[:mid]

            # Temporarily apply test_subset as lazy, others eager
            for e in self.graph.edges:
                if e in test_subset:
                    e.safety_class = "SAFE_LAZY"
                else:
                    e.safety_class = "EAGER_REQUIRED"

            is_clean = self.verify_fn()
            if is_clean:
                # First half is clean, problem lies in second half
                candidates = candidates[mid:]
                if len(candidates) == 1:
                    problematic.append(candidates[0])
                    break
            else:
                # Problem is in first half
                candidates = test_subset
                if len(candidates) == 1:
                    problematic.append(candidates[0])
                    break

        return problematic, [e for e in lazy_edges if e not in problematic]
