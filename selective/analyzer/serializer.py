"""
Serializer for Selective Package Graph.
Supports JSON format and mmap-friendly fast binary format.
"""

import struct
import json
from pathlib import Path
from typing import Union, Dict, Any, List
from selective.analyzer.graph_builder import PackageGraph, GraphNode, GraphEdge

MAGIC_HEADER = b"SLTV"
FORMAT_VERSION = 2

class GraphSerializer:
    @staticmethod
    def save_json(graph: PackageGraph, file_path: Union[str, Path]):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(graph.to_json(indent=2), encoding="utf-8")

    @staticmethod
    def load_json(file_path: Union[str, Path]) -> PackageGraph:
        path = Path(file_path)
        return PackageGraph.from_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def save_binary(graph: PackageGraph, file_path: Union[str, Path]):
        """
        Binary layout:
        [4 bytes MAGIC][2 bytes VERSION][4 bytes JSON_LEN][JSON PAYLOAD]
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        json_bytes = graph.to_json(indent=None).encode("utf-8")
        header = struct.pack(">4sHI", MAGIC_HEADER, FORMAT_VERSION, len(json_bytes))
        
        with open(path, "wb") as f:
            f.write(header)
            f.write(json_bytes)

    @staticmethod
    def load_binary(file_path: Union[str, Path]) -> PackageGraph:
        path = Path(file_path)
        with open(path, "rb") as f:
            header = f.read(10)
            magic, version, length = struct.unpack(">4sHI", header)
            if magic != MAGIC_HEADER:
                raise ValueError(f"Invalid binary magic bytes: {magic}")
            payload_bytes = f.read(length)
            return PackageGraph.from_json(payload_bytes.decode("utf-8"))
