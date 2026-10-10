"""Permanent, versioned station graph files, replaced only by explicit updates."""
import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path

from src.domain.line_graph import LineGraph, validate_line_graph

logger = logging.getLogger(__name__)
GRAPH_CACHE_VERSION = 1
GRAPH_CACHE_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    / "ratp-calendrier-travaux" / "line_graphs"
)


def _cache_directory() -> Path:
    return Path(os.environ.get(
        "LINE_GRAPH_DATA_DIR", os.environ.get("LINE_GRAPH_CACHE_DIR", str(GRAPH_CACHE_DIR)),
    ))


def _cache_path(navitia_id: str) -> Path:
    return _cache_directory() / f"{hashlib.sha256(navitia_id.encode()).hexdigest()}.json"


def read_graph(navitia_id: str) -> tuple[LineGraph, float] | None:
    path = _cache_path(navitia_id)
    try:
        with path.open(encoding="utf-8") as stream:
            entry = json.load(stream)
        if entry["version"] != GRAPH_CACHE_VERSION or entry["navitia_id"] != navitia_id:
            logger.warning("Ignoring obsolete station graph cache for %s", navitia_id)
            return None
        graph = entry["graph"]
        validate_line_graph(graph)
        fetched_at = float(entry["fetched_at"])
        if not 0 < fetched_at <= time.time():
            raise ValueError("Invalid graph cache timestamp")
        return graph, fetched_at
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Ignoring invalid station graph cache for %s: %s", navitia_id, exc)
        return None


def write_graph(navitia_id: str, graph: LineGraph, fetched_at: float) -> None:
    validate_line_graph(graph)
    directory = _cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = _cache_path(navitia_id)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump({
                "version": GRAPH_CACHE_VERSION, "navitia_id": navitia_id,
                "fetched_at": fetched_at, "graph": graph,
            }, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
