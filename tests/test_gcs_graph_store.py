import json
import time
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import Forbidden, NotFound
from google.auth.exceptions import DefaultCredentialsError

from src.services import line_graph_cache as store


@pytest.fixture
def graph():
    return {"stations": {
        "a": {"name": "A", "lat": 48.0, "lon": 2.0, "neighbors": ["b"]},
        "b": {"name": "B", "lat": 48.1, "lon": 2.1, "neighbors": ["a"]},
    }}


@pytest.fixture
def bucket(tmp_path, monkeypatch):
    monkeypatch.setenv("LINE_GRAPH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BUCKET_PREFIX", "/graphs/")
    client = Mock()
    monkeypatch.setattr(store.storage, "Client", Mock(return_value=client))
    return client, client.bucket.return_value.blob.return_value


def payload(graph, navitia_id="test"):
    return json.dumps({
        "version": store.GRAPH_CACHE_VERSION, "navitia_id": navitia_id,
        "fetched_at": time.time(), "graph": graph,
    }).encode()


def test_download_validates_and_populates_local_cache(bucket, graph):
    client, blob = bucket
    blob.download_as_bytes.return_value = payload(graph)
    assert store.read_graph("test")[0] == graph
    client.bucket.assert_called_once_with("test-bucket")
    client.bucket.return_value.blob.assert_called_once_with(
        f"graphs/{store._cache_path('test').name}",
    )
    assert store._cache_path("test").is_file()
    assert store.read_graph("test")[0] == graph
    blob.download_as_bytes.assert_called_once_with(timeout=30)
    blob.upload_from_string.assert_not_called()


def test_missing_object_is_not_cached(bucket):
    _, blob = bucket
    blob.download_as_bytes.side_effect = NotFound("missing")
    assert store.read_graph("test") is None
    assert not store._cache_path("test").exists()


@pytest.mark.parametrize("data", [b"{", b"{}", b"null"])
def test_invalid_object_never_populates_local_cache(bucket, data):
    _, blob = bucket
    blob.download_as_bytes.return_value = data
    with pytest.raises(ValueError, match="Invalid bucket"):
        store.read_graph("test")
    assert not store._cache_path("test").exists()


def test_mismatched_object_is_rejected(bucket, graph):
    _, blob = bucket
    blob.download_as_bytes.return_value = payload(graph, "another-line")
    with pytest.raises(ValueError, match="Invalid bucket"):
        store.read_graph("test")


def test_corrupt_local_file_is_recovered_from_bucket(bucket, graph):
    _, blob = bucket
    store._cache_path("test").write_text("{")
    blob.download_as_bytes.return_value = payload(graph)
    assert store.read_graph("test")[0] == graph
    assert json.loads(store._cache_path("test").read_text())["graph"] == graph


@pytest.mark.parametrize("error", [Forbidden("denied"), DefaultCredentialsError("no credentials")])
def test_download_failure_is_explicit(bucket, error):
    _, blob = bucket
    blob.download_as_bytes.side_effect = error
    with pytest.raises(OSError, match="Unable to download"):
        store.read_graph("test")
    assert not store._cache_path("test").exists()


def test_write_uploads_then_publishes_local_file(bucket, graph):
    _, blob = bucket
    store.write_graph("test", graph, time.time())
    args, kwargs = blob.upload_from_string.call_args
    assert json.loads(args[0])["graph"] == graph
    assert kwargs == {"content_type": "application/json", "timeout": 30}
    assert store.read_graph("test")[0] == graph


def test_failed_upload_preserves_local_file(bucket, graph):
    _, blob = bucket
    old = payload(graph)
    store._cache_path("test").write_bytes(old)
    blob.upload_from_string.side_effect = Forbidden("denied")
    with pytest.raises(OSError, match="Unable to upload"):
        store.write_graph("test", graph, time.time())
    assert store._cache_path("test").read_bytes() == old


def test_invalid_timestamp_never_uploads(bucket, graph):
    _, blob = bucket
    with pytest.raises(ValueError, match="timestamp"):
        store.write_graph("test", graph, 0)
    blob.upload_from_string.assert_not_called()


def test_local_write_failure_after_upload_is_not_hidden(bucket, graph, monkeypatch):
    _, blob = bucket
    monkeypatch.setattr(store, "_write_local", Mock(side_effect=PermissionError("read only")))
    with pytest.raises(PermissionError, match="read only"):
        store.write_graph("test", graph, time.time())
    blob.upload_from_string.assert_called_once()


def test_empty_prefix_uses_existing_hashed_filename(bucket, graph, monkeypatch):
    client, blob = bucket
    monkeypatch.setenv("GCS_BUCKET_PREFIX", "")
    blob.download_as_bytes.return_value = payload(graph)
    store.read_graph("test")
    client.bucket.return_value.blob.assert_called_once_with(store._cache_path("test").name)
