import asyncio
import json
import os
import time
import unicodedata

import httpx
import pytest

from src.domain.line_graph import LineGraphBuilder, validate_line_graph
from src.services import line_graph_cache, navitia_client


def journey(*station_ids):
    return {"stop_times": [
        {"stop_point": {
            "id": f"platform:{station_id}",
            "name": station_id,
            "coord": {"lat": "48.85", "lon": "2.35"},
            "stop_area": {"id": station_id, "name": station_id},
        }}
        for station_id in station_ids
    ]}


def build(*paths):
    builder = LineGraphBuilder()
    for path in paths:
        builder.add_journey(journey(*path))
    return builder.build()


def edges(graph):
    return {
        tuple(sorted((station_id, neighbor)))
        for station_id, station in graph["stations"].items()
        for neighbor in station["neighbors"]
    }


def test_order_comes_from_stop_times_not_coordinates_or_ids():
    graph = build(["z", "a", "y", "b"])
    assert edges(graph) == {("a", "z"), ("a", "y"), ("b", "y")}


def test_express_short_turns_reverse_and_duplicates_do_not_add_shortcuts():
    graph = build(
        ["a", "b", "c", "d"], ["d", "c", "b", "a"], ["a", "b", "c", "d"],
        ["a", "c", "d"], ["d", "a"], ["b", "c"],
    )
    assert edges(graph) == {("a", "b"), ("b", "c"), ("c", "d")}


def test_distinct_branches_and_their_express_services():
    graph = build(
        ["a", "b", "c", "d"], ["a", "b", "e", "f"],
        ["a", "c", "d"], ["a", "e", "f"],
    )
    assert edges(graph) == {("a", "b"), ("b", "c"), ("c", "d"), ("b", "e"), ("e", "f")}


def test_loops_preserve_nonconsecutive_visits():
    graph = build(["a", "b", "c", "a", "d"])
    assert edges(graph) == {("a", "b"), ("b", "c"), ("a", "c"), ("a", "d")}


def test_express_shortcut_on_partially_overlapping_branch_is_removed():
    graph = build(["a", "b", "c", "d"], ["a", "c", "e", "f"])
    assert edges(graph) == {("a", "b"), ("b", "c"), ("c", "d"), ("c", "e"), ("e", "f")}


def test_loop_links_survive_an_overlapping_simple_path():
    graph = build(["a", "b", "c", "a", "d"], ["a", "b", "c", "e"])
    assert ("a", "c") in edges(graph)


def test_consecutive_platforms_collapse_without_self_links():
    assert edges(build(["a", "a", "b", "b", "c"])) == {("a", "b"), ("b", "c")}


def test_stop_area_coordinates_and_names_are_preferred():
    data = journey("a", "b")
    point = data["stop_times"][0]["stop_point"]
    point["coord"] = {}
    point["stop_area"].update({"name": "Station A", "coord": {"lat": "48", "lon": "2"}})
    builder = LineGraphBuilder()
    builder.add_journey(data)
    assert builder.build()["stations"]["a"]["name"] == "Station A"
    assert builder.build()["stations"]["a"]["lat"] == 48


@pytest.mark.parametrize("coord", [{}, {"lat": "nan", "lon": "2"}, {"lat": "91", "lon": "2"}])
def test_bad_coordinates_reject_build_without_bridging(coord):
    data = journey("a", "b", "c")
    data["stop_times"][1]["stop_point"]["coord"] = coord
    with pytest.raises(ValueError, match="coordinates"):
        LineGraphBuilder().add_journey(data)


def test_skipped_stops_are_retained_in_reference_path():
    data = journey("a", "b", "c")
    data["stop_times"][1]["skipped_stop"] = True
    builder = LineGraphBuilder()
    builder.add_journey(data)
    assert edges(builder.build()) == {("a", "b"), ("b", "c")}


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "")
    monkeypatch.delenv("LINE_GRAPH_DATA_DIR", raising=False)
    monkeypatch.delenv("LINE_GRAPH_CACHE_DIR", raising=False)
    monkeypatch.setattr(line_graph_cache, "GRAPH_CACHE_DIR", tmp_path)
    monkeypatch.setattr(navitia_client, "_line_stations_locks", {})
    return tmp_path


@pytest.mark.asyncio
async def test_all_pages_before_graph_build_and_memory_disk_cache(isolated_cache):
    calls = []

    def handler(request):
        page = int(request.url.params["start_page"])
        calls.append(page)
        assert request.url.path.endswith("/vehicle_journeys")
        assert request.url.params["data_freshness"] == "base_schedule"
        assert "since" not in request.url.params
        return httpx.Response(200, json={
            "pagination": {"total_result": 2},
            "vehicle_journeys": [journey("a", "c") if page == 0 else journey("a", "b", "c")],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph = await navitia_client.refresh_line_stations("test", "key", client)
        assert edges(graph) == {("a", "b"), ("b", "c")}
        assert calls == [0, 1]
        assert await navitia_client.fetch_line_stations("test") == graph
        assert await navitia_client.fetch_line_stations("test") == graph
        assert calls == [0, 1]
        assert len(list(isolated_cache.glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_concurrent_updates_reject_duplicate_builds(isolated_cache):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={
            "pagination": {"total_result": 1}, "vehicle_journeys": [journey("a", "b")],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await asyncio.gather(*[
            navitia_client.refresh_line_stations("test", "key", client) for _ in range(5)
        ], return_exceptions=True)
    assert results[0] == build(["a", "b"])
    assert all(isinstance(result, navitia_client.GraphRefreshInProgress) for result in results[1:])
    assert calls == 1


@pytest.mark.asyncio
async def test_force_refresh_replaces_cache(isolated_cache):
    old = build(["a", "b"])
    line_graph_cache.write_graph("test", old, time.time())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"pagination": {"total_result": 1}, "vehicle_journeys": [journey("a", "b", "c")]},
    ))) as client:
        graph = await navitia_client.refresh_line_stations("test", "key", client)
    assert "c" in graph["stations"]
    assert line_graph_cache.read_graph("test")[0] == graph


@pytest.mark.asyncio
async def test_old_persisted_graph_is_served_without_network_or_expiration(isolated_cache, monkeypatch):
    graph = build(["a", "b"])
    timestamp = time.time() - 365 * 24 * 60 * 60
    line_graph_cache.write_graph("test", graph, timestamp)
    async def unexpected(*args, **kwargs):
        pytest.fail("Public reads must never call Navitia")

    monkeypatch.setattr(navitia_client, "_fetch_line_graph", unexpected)
    assert await navitia_client.fetch_line_stations("test") == graph
    assert await navitia_client.fetch_line_stations("test") == graph
    assert line_graph_cache.read_graph("test")[1] == timestamp


@pytest.mark.asyncio
async def test_failed_second_page_never_persists_partial_graph(isolated_cache):
    def handler(request):
        if request.url.params["start_page"] == "1":
            return httpx.Response(503)
        return httpx.Response(200, json={
            "pagination": {"total_result": 2}, "vehicle_journeys": [journey("a", "b")],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await navitia_client.refresh_line_stations("test", "key", client)
    assert not list(isolated_cache.glob("*.json"))


@pytest.mark.asyncio
async def test_missing_collection_stop_times_are_recovered_from_detail(isolated_cache):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/lines/line:IDFM:test/vehicle_journeys"):
            return httpx.Response(200, json={
                "pagination": {"total_result": 2},
                "vehicle_journeys": [journey("a", "c"), {"id": "vj:full"}],
            })
        recovered = {**journey("a", "b", "c"), "id": "vj:full"}
        return httpx.Response(200, json={"vehicle_journeys": [recovered]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph = await navitia_client.refresh_line_stations("test", "key", client)
    assert edges(graph) == {("a", "b"), ("b", "c")}
    assert len(calls) == 2
    assert calls[-1].endswith("/vehicle_journeys/vj:full")


@pytest.mark.asyncio
async def test_empty_journey_is_logged_but_does_not_hide_valid_line(isolated_cache, caplog):
    def handler(request):
        if "/lines/" in request.url.path:
            return httpx.Response(200, json={
                "pagination": {"total_result": 2},
                "vehicle_journeys": [{"id": "vj:empty"}, journey("a", "b", "c")],
            })
        return httpx.Response(200, json={"vehicle_journeys": [{"id": "vj:empty"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph = await navitia_client.refresh_line_stations("test", "key", client)
    assert edges(graph) == {("a", "b"), ("b", "c")}
    assert "Ignoring empty vehicle journey vj:empty" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("details", [[], [{"id": "vj:other"}], [{"id": "vj:empty"}]])
async def test_missing_or_only_empty_journeys_cannot_produce_cached_graph(isolated_cache, details):
    def handler(request):
        if "/lines/" in request.url.path:
            return httpx.Response(200, json={
                "pagination": {"total_result": 1},
                "vehicle_journeys": [{"id": "vj:empty"}],
            })
        return httpx.Response(200, json={"vehicle_journeys": details})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            await navitia_client.refresh_line_stations("test", "key", client)
    assert not list(isolated_cache.glob("*.json"))


@pytest.mark.asyncio
async def test_invalid_new_build_does_not_replace_valid_cache(isolated_cache):
    old = build(["a", "b"])
    line_graph_cache.write_graph("test", old, time.time())
    original = next(isolated_cache.glob("*.json")).read_bytes()
    invalid = journey("a", "b", "c")
    invalid["stop_times"][1]["stop_point"]["coord"] = {}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"pagination": {"total_result": 1}, "vehicle_journeys": [invalid]},
    ))) as client:
        with pytest.raises(ValueError):
            await navitia_client.refresh_line_stations("test", "key", client)
    assert next(isolated_cache.glob("*.json")).read_bytes() == original
    assert await navitia_client.fetch_line_stations("test") == old


@pytest.mark.asyncio
async def test_disk_write_failure_is_reported_without_publishing_unpersisted_graph(isolated_cache, monkeypatch):
    old = build(["a", "b"])
    line_graph_cache.write_graph("test", old, time.time())

    def fail_write(*args):
        raise PermissionError("Read-only cache")

    monkeypatch.setattr(navitia_client, "write_graph", fail_write)
    def handler(request):
        return httpx.Response(200, json={
            "pagination": {"total_result": 1}, "vehicle_journeys": [journey("a", "b", "c")],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PermissionError):
            await navitia_client.refresh_line_stations("test", "key", client)
    assert line_graph_cache.read_graph("test")[0] == old
    assert await navitia_client.fetch_line_stations("test") == old


@pytest.mark.asyncio
async def test_api_returns_graph_and_exposes_failure(isolated_cache, monkeypatch):
    from src.main import app

    async def unexpected(*args, **kwargs):
        pytest.fail("Public reads must not have a Navitia dependency")

    monkeypatch.setattr(navitia_client, "_fetch_line_graph", unexpected)
    line_graph_cache.write_graph("C01372", build(["a", "b"]), time.time())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/lines/stations", params={"lines": "2"})
        assert response.status_code == 200
        assert edges(response.json()["2"]) == {("a", "b")}
        assert (await client.get("/lines/stations", params={"lines": "unknown"})).status_code == 422
        assert (await client.get("/lines/stations", params={"lines": "2", "refresh": "true"})).status_code == 422
        response = await client.get("/lines/stations", params={"lines": "1"})
        assert response.status_code == 503
        assert "administrator" in response.json()["detail"]


@pytest.fixture
def admin_client(isolated_cache, monkeypatch):
    from src.main import app, get_client
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    app.dependency_overrides[get_client] = lambda: None
    try:
        yield httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test")
    finally:
        app.dependency_overrides.pop(get_client, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong"}])
async def test_admin_refresh_rejects_unauthorized_requests(admin_client, headers, monkeypatch):
    import src.main as main
    async def unexpected(*args, **kwargs):
        pytest.fail("Unauthorized request triggered graph refresh")
    monkeypatch.setattr(main, "refresh_line_stations", unexpected)
    async with admin_client as client:
        response = await client.post("/admin/lines/stations/refresh?lines=2", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_refresh_is_disabled_without_secret(admin_client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY")
    async with admin_client as client:
        response = await client.post("/admin/lines/stations/refresh?lines=2", headers={"X-Admin-Key": "anything"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_admin_refresh_updates_persistent_data_and_deduplicates_lines(admin_client, monkeypatch):
    calls = []
    async def mock_build(navitia_id, api_key, client):
        calls.append(navitia_id)
        return build(["a", "b", "c"])
    monkeypatch.setattr(navitia_client, "_fetch_line_graph", mock_build)
    async with admin_client as client:
        response = await client.post(
            "/admin/lines/stations/refresh?lines=2,2",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 200
        assert response.json() == {"lines": {"2": {"status": "updated", "station_count": 3, "link_count": 2}}}
        graph_response = await client.get("/lines/stations?lines=2")
        assert edges(graph_response.json()["2"]) == {("a", "b"), ("b", "c")}
    assert calls == ["C01372"]
    assert line_graph_cache.read_graph("C01372") is not None


@pytest.mark.asyncio
async def test_admin_all_updates_every_line_sequentially(admin_client, monkeypatch):
    from src.domain.lines import LINE_REGISTRY
    calls = []
    active = 0

    async def mock_build(navitia_id, api_key, client):
        nonlocal active
        active += 1
        assert active == 1
        await asyncio.sleep(0)
        calls.append(navitia_id)
        active -= 1
        return build(["a", "b"])

    monkeypatch.setattr(navitia_client, "_fetch_line_graph", mock_build)
    async with admin_client as client:
        response = await client.post(
            "/admin/lines/stations/refresh?lines=all",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 200
        assert set(response.json()["lines"]) == set(LINE_REGISTRY)
        assert (await client.get("/lines/stations?lines=all")).status_code == 422
    assert calls == [line.navitia_id for line in LINE_REGISTRY.values()]


@pytest.mark.asyncio
async def test_script_missing_only_preserves_existing_files_and_continues_after_failure(
    isolated_cache, monkeypatch,
):
    import scratch.generate_static_graph as script
    monkeypatch.setenv("NAVITIA_API_KEY", "test-key")
    monkeypatch.setattr(script, "load_dotenv", lambda *args: None)
    line_graph_cache.write_graph("C01371", build(["a", "b"]), time.time())
    original = line_graph_cache._cache_path("C01371").read_bytes()
    calls = []

    async def mock_refresh(navitia_id, api_key, client):
        calls.append(navitia_id)
        if navitia_id == "C01372":
            raise httpx.ReadTimeout("Upstream timeout")
        graph = build(["a", "b", "c"])
        line_graph_cache.write_graph(navitia_id, graph, time.time())
        return graph

    monkeypatch.setattr(script, "refresh_line_stations", mock_refresh)
    with pytest.raises(SystemExit, match="2"):
        await script.generate_static_graph(["1", "2", "3"], missing_only=True)
    assert calls == ["C01372", "C01373"]
    assert line_graph_cache._cache_path("C01371").read_bytes() == original
    assert line_graph_cache.read_graph("C01373") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("lines", ["", "unknown", "2,unknown"])
async def test_admin_validates_entire_selection_before_updating(admin_client, monkeypatch, lines):
    async def unexpected(*args, **kwargs):
        pytest.fail("Invalid batch triggered graph refresh")
    monkeypatch.setattr(navitia_client, "_fetch_line_graph", unexpected)
    async with admin_client as client:
        response = await client.post(
            "/admin/lines/stations/refresh", params={"lines": lines},
            headers={"X-Admin-Key": "test-admin-key"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_reports_batch_failures_and_retains_old_file(admin_client, monkeypatch, isolated_cache):
    old = build(["a", "b"])
    line_graph_cache.write_graph("C01742", old, time.time())
    original = line_graph_cache._cache_path("C01742").read_bytes()

    async def mock_build(navitia_id, api_key, client):
        if navitia_id == "C01742":
            raise ValueError("Invalid Navitia data")
        return build(["a", "b", "c"])
    monkeypatch.setattr(navitia_client, "_fetch_line_graph", mock_build)
    async with admin_client as client:
        response = await client.post(
            "/admin/lines/stations/refresh?lines=2,A",
            headers={"X-Admin-Key": "test-admin-key"},
        )
    assert response.status_code == 502
    assert response.json()["lines"]["2"]["status"] == "updated"
    assert response.json()["lines"]["A"]["status"] == "failed"
    assert line_graph_cache._cache_path("C01742").read_bytes() == original


@pytest.mark.asyncio
async def test_public_read_does_not_wait_for_slow_update_and_new_file_is_visible(isolated_cache, monkeypatch):
    old = build(["a", "b"])
    new = build(["a", "b", "c"])
    line_graph_cache.write_graph("C01372", old, time.time())
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow_build(*args):
        started.set()
        await finish.wait()
        return new
    monkeypatch.setattr(navitia_client, "_fetch_line_graph", slow_build)
    task = asyncio.create_task(navitia_client.refresh_line_stations("C01372", "key"))
    try:
        await asyncio.wait_for(started.wait(), 1)
        assert await asyncio.wait_for(navitia_client.fetch_line_stations("C01372"), 0.5) == old
        with pytest.raises(navitia_client.GraphRefreshInProgress):
            await navitia_client.refresh_line_stations("C01372", "key")
        finish.set()
        await task
        assert await navitia_client.fetch_line_stations("C01372") == new
    finally:
        finish.set()
        await task


@pytest.mark.asyncio
async def test_missing_public_graph_never_builds_on_demand(isolated_cache, monkeypatch):
    async def unexpected(*args, **kwargs):
        pytest.fail("Missing persistent graph triggered Navitia")
    monkeypatch.setattr(navitia_client, "_fetch_line_graph", unexpected)
    with pytest.raises(FileNotFoundError):
        await navitia_client.fetch_line_stations("test")


@pytest.mark.asyncio
async def test_admin_busy_response_does_not_trigger_another_build(admin_client, monkeypatch):
    import src.main as main

    async def busy(*args, **kwargs):
        raise navitia_client.GraphRefreshInProgress("Already updating")

    monkeypatch.setattr(main, "refresh_line_stations", busy)
    async with admin_client as client:
        response = await client.post(
            "/admin/lines/stations/refresh?lines=2",
            headers={"X-Admin-Key": "test-admin-key"},
        )
    assert response.status_code == 409
    assert response.json()["lines"]["2"]["status"] == "busy"


def test_data_directory_configuration_and_legacy_compatibility(isolated_cache, monkeypatch):
    monkeypatch.setenv("LINE_GRAPH_CACHE_DIR", str(isolated_cache / "legacy"))
    assert line_graph_cache._cache_directory() == isolated_cache / "legacy"
    monkeypatch.setenv("LINE_GRAPH_DATA_DIR", str(isolated_cache / "permanent"))
    assert line_graph_cache._cache_directory() == isolated_cache / "permanent"
    line_graph_cache.write_graph("test", build(["a", "b"]), time.time())
    assert line_graph_cache.read_graph("test") is not None
    assert len(list((isolated_cache / "permanent").glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_persisted_graph_survives_a_new_process(isolated_cache):
    import subprocess
    import sys
    line_graph_cache.write_graph("test", build(["a", "b"]), time.time() - 365 * 86400)
    result = subprocess.run(
        [sys.executable, "-c",
         "import asyncio; from src.services.navitia_client import fetch_line_stations; "
         "graph = asyncio.run(fetch_line_stations('test')); "
         "assert graph['stations']['a']['neighbors'] == ['b']; print('persisted')"],
        env={**os.environ, "LINE_GRAPH_DATA_DIR": str(isolated_cache)},
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.strip() == "persisted"


@pytest.mark.parametrize("mutation", ["version", "corrupt", "asymmetric", "empty"])
def test_invalid_or_old_disk_cache_is_ignored(isolated_cache, mutation, caplog):
    line_graph_cache.write_graph("test", build(["a", "b"]), time.time())
    path = next(isolated_cache.glob("*.json"))
    entry = json.loads(path.read_text())
    if mutation == "version":
        entry["version"] = 0
    elif mutation == "asymmetric":
        entry["graph"]["stations"]["b"]["neighbors"] = []
    elif mutation == "empty":
        entry["graph"] = None
    path.write_text("invalid json" if mutation == "corrupt" else json.dumps(entry))
    assert line_graph_cache.read_graph("test") is None
    assert "Ignoring" in caplog.text


def test_line_2_exact_chain():
    ids = [str(index) for index in range(25)]
    graph = build(ids, ids[::-1], ids[1:], ids[::2])
    assert len(graph["stations"]) == 25
    assert len(edges(graph)) == 24
    for index, station_id in enumerate(ids):
        assert set(graph["stations"][station_id]["neighbors"]) == set(ids[max(0, index - 1):index] + ids[index + 1:index + 2])


@pytest.mark.skipif(os.getenv("RUN_NAVITIA_GRAPH_SMOKE") != "1", reason="Explicit live test opt-in required")
@pytest.mark.asyncio
async def test_live_line_2(monkeypatch):
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ["NAVITIA_API_KEY"]
    started = time.time()
    graph = await navitia_client.refresh_line_stations("C01372", key)
    disk_entry = line_graph_cache.read_graph("C01372")
    assert disk_entry is not None and disk_entry[1] >= started
    validate_line_graph(graph)
    expected = [
        "Porte Dauphine", "Victor Hugo", "Charles de Gaulle - Etoile", "Ternes",
        "Courcelles", "Monceau", "Villiers", "Rome", "Place de Clichy", "Blanche",
        "Pigalle", "Anvers", "Barbes - Rochechouart", "La Chapelle", "Stalingrad",
        "Jaures", "Colonel Fabien", "Belleville", "Couronnes", "Menilmontant",
        "Pere Lachaise", "Philippe Auguste", "Alexandre Dumas", "Avron", "Nation",
    ]

    def normalize(name):
        return "".join(c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c))

    stations = graph["stations"]
    by_name = {normalize(station["name"]): station_id for station_id, station in stations.items()}
    assert set(by_name) == set(expected)
    assert len(stations) == 25
    assert len(edges(graph)) == 24
    for index, name in enumerate(expected):
        wanted = expected[max(0, index - 1):index] + expected[index + 1:index + 2]
        assert set(stations[by_name[name]]["neighbors"]) == {by_name[neighbor] for neighbor in wanted}
    async def unexpected_network(*args, **kwargs):
        pytest.fail("A fresh persistent cache must not call Navitia")

    monkeypatch.setattr(navitia_client, "_fetch_line_graph", unexpected_network)
    assert await navitia_client.fetch_line_stations("C01372") == graph


@pytest.mark.skipif(os.getenv("RUN_NAVITIA_GRAPH_SMOKE") != "1", reason="Explicit live test opt-in required")
@pytest.mark.asyncio
async def test_live_rer_a():
    from dotenv import load_dotenv
    load_dotenv()
    started = time.time()
    graph = await navitia_client.refresh_line_stations("C01742", os.environ["NAVITIA_API_KEY"])
    disk_entry = line_graph_cache.read_graph("C01742")
    assert disk_entry is not None and disk_entry[1] >= started
    stations = graph["stations"]
    assert len(stations) == 46
    assert len(edges(graph)) == 45
    assert {station["name"] for station in stations.values() if len(station["neighbors"]) == 1} == {
        "Saint-Germain-en-Laye", "Poissy", "Cergy le Haut", "Marne-la-Vallée - Chessy", "Boissy-Saint-Léger",
    }
    by_name = {station["name"]: station_id for station_id, station in stations.items()}
    for junction, expected in {
        "Nanterre - Préfecture": {"Nanterre Université", "Houilles - Carrières-sur-Seine", "La Défense"},
        "Maisons-Laffitte": {"Sartrouville", "Achères Grand Cormier", "Achères Ville"},
        "Vincennes": {"Nation", "Fontenay-sous-Bois", "Val de Fontenay"},
    }.items():
        assert {stations[neighbor]["name"] for neighbor in stations[by_name[junction]]["neighbors"]} == expected
