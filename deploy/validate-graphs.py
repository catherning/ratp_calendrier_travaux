#!/usr/bin/env python3
"""Validate every envelope before uploading any unchanged hashed JSON object."""
import hashlib
import json
import math
import re
import runpy
import sys
import time
from pathlib import Path

from config import unique_object


def validate_directory(directory):
    root = Path(directory).resolve(strict=True)
    if any(ord(char) < 32 for char in str(root)):
        raise ValueError("Graph directory cannot contain control characters")
    if not root.is_dir():
        raise ValueError("Graph input must be a directory")
    files = sorted(root.glob("*.json"))
    if not files:
        raise ValueError("No graph JSON files found")
    validate_graph = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "src/domain/line_graph.py")
    )["validate_line_graph"]
    for path in files:
        if path.is_symlink() or not re.fullmatch(r"[a-f0-9]{64}\.json", path.name):
            raise ValueError(f"Expected a regular SHA-256 filename: {path.name}")
        entry = json.loads(path.read_text(), object_pairs_hook=unique_object,
                           parse_constant=lambda value: (_ for _ in ()).throw(
                               ValueError(f"Invalid JSON constant: {value}")))
        if not isinstance(entry, dict) or set(entry) != {"version", "navitia_id", "fetched_at", "graph"}:
            raise ValueError(f"Invalid envelope: {path.name}")
        if type(entry["version"]) is not int or entry["version"] != 1:
            raise ValueError(f"Unsupported version: {path.name}")
        navitia_id = entry["navitia_id"]
        if not isinstance(navitia_id, str) or not re.fullmatch(r"C[0-9]{5}", navitia_id):
            raise ValueError(f"Invalid Navitia line ID: {path.name}")
        if path.stem != hashlib.sha256(navitia_id.encode()).hexdigest():
            raise ValueError(f"Filename does not match envelope Navitia ID: {path.name}")
        timestamp = entry["fetched_at"]
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or not 0 < timestamp <= time.time():
            raise ValueError(f"Invalid fetched_at: {path.name}")
        validate_graph(entry["graph"])
    return files


if __name__ == "__main__":
    try:
        for graph_file in validate_directory(sys.argv[1]):
            print(graph_file)
    except (ValueError, OSError, IndexError, TypeError, KeyError) as error:
        sys.exit(f"Graph validation error: {error}")
