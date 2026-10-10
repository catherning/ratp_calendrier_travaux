from dataclasses import FrozenInstanceError, asdict
import json

import httpx
import pytest

from src.domain.lines import (
    ALL_CODES,
    LINE_METADATA_PATH,
    LINE_REGISTRY,
    METRO_CODES,
    RER_CODES,
    TRANSILIEN_CODES,
    get_line,
    load_line_registry,
)


def test_catalogue_order_and_mode_lists_are_consistent():
    entries = json.loads(LINE_METADATA_PATH.read_text(encoding="utf-8"))
    assert ALL_CODES == [entry["code"] for entry in entries] == list(LINE_REGISTRY)
    assert METRO_CODES == [str(i) for i in range(1, 15)]
    assert RER_CODES == ["A", "B", "C", "D", "E"]
    assert TRANSILIEN_CODES == ["H", "J", "K", "L", "N", "P", "R", "U"]
    assert ALL_CODES == METRO_CODES + RER_CODES + TRANSILIEN_CODES
    assert [asdict(line) for line in LINE_REGISTRY.values()] == entries
    assert get_line("15") is None
    assert get_line("unknown") is None


def test_official_rer_and_transilien_ids():
    expected = {
        "A": "C01742", "B": "C01743", "C": "C01727", "D": "C01728", "E": "C01729",
        "H": "C01737", "J": "C01739", "K": "C01738", "L": "C01740",
        "N": "C01736", "P": "C01730", "R": "C01731", "U": "C01741",
    }
    assert {code: LINE_REGISTRY[code].navitia_id for code in expected} == expected
    assert len({line.navitia_id for line in LINE_REGISTRY.values()}) == len(ALL_CODES)


def test_line_metadata_remains_immutable():
    with pytest.raises(FrozenInstanceError):
        LINE_REGISTRY["4"].color = "000000"


def test_loading_catalogue_is_independent_of_working_directory_and_graphs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LINE_GRAPH_DATA_DIR", str(tmp_path / "no-graphs"))
    assert load_line_registry() == LINE_REGISTRY


@pytest.mark.parametrize("field,value", [
    ("navitia_id", "line:IDFM:C01740"),
    ("code", ""),
    ("mode", "invalid"),
    ("color", "#FF0000"),
    ("text_color", "not-a-colour"),
    ("name", ""),
    ("logo_url", "not-a-url"),
    ("extra", "unexpected"),
])
def test_invalid_fields_fail_explicitly(tmp_path, field, value):
    entry = asdict(LINE_REGISTRY["4"])
    entry[field] = value
    path = tmp_path / "lines.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(ValueError, match="Unable to load line catalogue"):
        load_line_registry(path)


@pytest.mark.parametrize("field,message", [
    ("code", "Duplicate line code"),
    ("navitia_id", "Duplicate Navitia ID"),
])
def test_duplicate_identifiers_fail_explicitly(tmp_path, field, message):
    first = asdict(LINE_REGISTRY["4"])
    second = asdict(LINE_REGISTRY["A"])
    second[field] = first[field]
    path = tmp_path / "lines.json"
    path.write_text(json.dumps([first, second]), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_line_registry(path)


@pytest.mark.parametrize("content", ["{", "{}", "[]"])
def test_invalid_or_empty_catalogue_fails_explicitly(tmp_path, content):
    path = tmp_path / "lines.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="catalogue"):
        load_line_registry(path)


def test_missing_catalogue_fails_explicitly(tmp_path):
    with pytest.raises(ValueError, match="Unable to load line catalogue"):
        load_line_registry(tmp_path / "missing.json")


@pytest.mark.asyncio
async def test_lines_endpoint_preserves_response_shape_without_graphs(tmp_path, monkeypatch):
    from src.main import app
    monkeypatch.setenv("LINE_GRAPH_DATA_DIR", str(tmp_path / "no-graphs"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/lines")
    assert response.status_code == 200
    assert response.json() == [asdict(line) for line in LINE_REGISTRY.values()]
