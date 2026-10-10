"""Versioned graphs on local disk, optionally backed by Cloud Storage."""
import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path

from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.auth.exceptions import GoogleAuthError
from google.cloud import storage

from src.domain.line_graph import LineGraph, validate_line_graph

logger = logging.getLogger(__name__)
GRAPH_CACHE_VERSION = 1
GRAPH_CACHE_DIR = Path(__file__).resolve().parents[2] / "line_graphs"


def _cache_directory() -> Path:
    return Path(os.environ.get(
        "LINE_GRAPH_DATA_DIR", os.environ.get("LINE_GRAPH_CACHE_DIR", str(GRAPH_CACHE_DIR)),
    ))


def _cache_path(navitia_id: str) -> Path:
    return _cache_directory() / f"{hashlib.sha256(navitia_id.encode()).hexdigest()}.json"


def read_graph(navitia_id: str) -> tuple[LineGraph, float] | None:
    entry = _read_local_graph(navitia_id)
    if entry is not None or not os.environ.get("GCS_BUCKET_NAME"):
        return entry
    try:
        payload = _blob(navitia_id).download_as_bytes(timeout=30)
    except NotFound:
        logger.warning("Station graph missing from bucket for %s", navitia_id)
        return None
    except (GoogleAPICallError, GoogleAuthError) as exc:
        logger.error("Unable to download station graph for %s: %s", navitia_id, exc)
        raise OSError(f"Unable to download station graph for {navitia_id}") from exc
    try:
        entry = _validate_entry(json.loads(payload), navitia_id)
    except (ValueError, KeyError, TypeError) as exc:
        logger.error("Invalid bucket station graph for %s: %s", navitia_id, exc)
        raise ValueError(f"Invalid bucket station graph for {navitia_id}") from exc
    _write_local(navitia_id, payload)
    return entry


def _blob(navitia_id: str) -> storage.Blob:
    prefix = os.environ.get("GCS_BUCKET_PREFIX", "").strip("/")
    name = _cache_path(navitia_id).name
    object_name = f"{prefix}/{name}" if prefix else name
    return storage.Client().bucket(os.environ["GCS_BUCKET_NAME"]).blob(object_name)


def _validate_entry(entry: dict, navitia_id: str) -> tuple[LineGraph, float]:
    if entry["version"] != GRAPH_CACHE_VERSION or entry["navitia_id"] != navitia_id:
        raise ValueError("Obsolete or mismatched station graph")
    graph = entry["graph"]
    validate_line_graph(graph)
    fetched_at = float(entry["fetched_at"])
    if not 0 < fetched_at <= time.time():
        raise ValueError("Invalid graph cache timestamp")
    return graph, fetched_at


def _read_local_graph(navitia_id: str) -> tuple[LineGraph, float] | None:
    path = _cache_path(navitia_id)
    try:
        with path.open(encoding="utf-8") as stream:
            entry = json.load(stream)
        return _validate_entry(entry, navitia_id)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Ignoring invalid station graph cache for %s: %s", navitia_id, exc)
        return None


def write_graph(navitia_id: str, graph: LineGraph, fetched_at: float) -> None:
    validate_line_graph(graph)
    entry = {
        "version": GRAPH_CACHE_VERSION, "navitia_id": navitia_id,
        "fetched_at": fetched_at, "graph": graph,
    }
    _validate_entry(entry, navitia_id)
    payload = json.dumps(entry, ensure_ascii=False).encode("utf-8")
    if os.environ.get("GCS_BUCKET_NAME"):
        try:
            _blob(navitia_id).upload_from_string(
                payload, content_type="application/json", timeout=30,
            )
        except (GoogleAPICallError, GoogleAuthError) as exc:
            logger.error("Unable to upload station graph for %s: %s", navitia_id, exc)
            raise OSError(f"Unable to upload station graph for {navitia_id}") from exc
    _write_local(navitia_id, payload)


def _write_local(navitia_id: str, payload: bytes) -> None:
    directory = _cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = _cache_path(navitia_id)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
