import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from src.domain.disruptions import normalize_line_disruptions
from src.domain.lines import ALL_CODES, LINE_REGISTRY
from src.domain.statistics import build_statistics
from src import main


def disruption(impact_id="shared", effect="NO_SERVICE", cause="travaux", periods=None):
    return {
        "impact_id": impact_id,
        "severity": {"effect": effect},
        "cause": cause,
        "application_periods": periods or [
            {"begin": "20990101T100000", "end": "20990101T200000"},
            {"begin": "20990102T100000", "end": "20990102T200000"},
        ],
    }


def normalized(code, *items):
    return normalize_line_disruptions({"disruptions": list(items)}, LINE_REGISTRY[code])


def test_statistics_unique_impacts_periods_ranking_and_partial_counts():
    reports = {code: [] for code in ALL_CODES}
    reports["1"] = normalized("1", disruption(), disruption(), disruption(
        "second", "REDUCED_SERVICE", "maintenance",
    ))
    reports["A"] = normalized("A", disruption())
    reports["2"] = None
    result = build_statistics(reports, datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert result.total_disruptions == 2
    assert result.lines_with_disruptions == 2
    assert result.lines_without_disruptions == len(ALL_CODES) - 3
    assert result.failed_lines == ["2"]
    assert [line.code for line in result.lines[:2]] == ["1", "A"]
    assert result.lines[0].disruption_count == 2
    assert result.lines[-1].disruption_count is None
    assert sum(item.count for item in result.effects) == 2
    assert {item.type: item.count for item in result.causes} == {"travaux": 1, "maintenance": 1}


def test_statistics_filtering_current_future_and_paris_time():
    reports = {code: [] for code in ALL_CODES}
    reports["1"] = normalized(
        "1",
        disruption("past", periods=[{"begin": "20261010T090000", "end": "20261010T115959"}]),
        disruption("current", periods=[{"begin": "20261010T090000", "end": "20261010T120000"}]),
        disruption("future"),
        disruption("irrelevant", cause="perturbation"),
        disruption("information", effect="UNKNOWN_EFFECT"),
        {**disruption("elevator"), "tags": ["ascenseur"]},
        disruption("missing-cause", cause=""),
    )
    result = build_statistics(reports, datetime(2026, 10, 10, 10, tzinfo=timezone.utc))
    assert result.total_disruptions == 3
    assert {item.type: item.count for item in result.causes} == {"travaux": 2, "unknown": 1}


def test_statistics_considers_all_periods_not_only_the_last_start():
    reports = {code: [] for code in ALL_CODES}
    reports["1"] = normalized("1", disruption(periods=[
        {"begin": "20261001T100000", "end": "20261101T200000"},
        {"begin": "20261002T100000", "end": "20261002T200000"},
    ]))
    assert build_statistics(reports, datetime(2026, 10, 10, tzinfo=timezone.utc)).total_disruptions == 1


def test_statistics_empty_network():
    result = build_statistics({code: [] for code in ALL_CODES}, datetime.now(timezone.utc))
    assert result.total_disruptions == result.lines_with_disruptions == 0
    assert result.lines_without_disruptions == result.total_lines
    assert result.effects == result.causes == result.failed_lines == []


@pytest.fixture
def statistics_client(monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "test-key")
    monkeypatch.setitem(main.app.dependency_overrides, main.get_client, lambda: None)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.asyncio
async def test_statistics_endpoint_all_lines_bounded_requests_partial_errors(statistics_client, monkeypatch):
    calls = []
    in_flight = 0
    peak = 0

    async def fetch(navitia_id, api_key, client):
        nonlocal in_flight, peak
        calls.append(navitia_id)
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        if navitia_id == LINE_REGISTRY["2"].navitia_id:
            raise httpx.ReadTimeout("Upstream timeout")
        return {"disruptions": [disruption()]}

    monkeypatch.setattr(main, "fetch_line_reports", fetch)
    async with statistics_client as client:
        response = await client.get("/statistics")
    assert response.status_code == 200
    data = response.json()
    assert set(calls) == {LINE_REGISTRY[code].navitia_id for code in ALL_CODES}
    assert len(calls) == len(set(calls))
    assert 1 < peak <= 4
    assert data["failed_lines"] == ["2"]
    assert data["total_disruptions"] == 1
    assert data["lines_with_disruptions"] == len(ALL_CODES) - 1
    assert data["lines_without_disruptions"] == 0
    assert data["lines"][-1]["disruption_count"] is None
    assert data["effects"] == [{"type": "NO_SERVICE", "count": 1}]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "invalid-json"])
async def test_statistics_endpoint_all_failures_are_not_zeroes(statistics_client, monkeypatch, failure):
    async def fetch(*args, **kwargs):
        if failure == "timeout":
            raise httpx.ReadTimeout("Upstream timeout")
        raise ValueError("Invalid JSON")

    monkeypatch.setattr(main, "fetch_line_reports", fetch)
    async with statistics_client as client:
        response = await client.get("/statistics")
    assert response.status_code == 502
    assert "total_disruptions" not in response.json()


@pytest.mark.asyncio
async def test_statistics_missing_key_does_not_fetch(statistics_client, monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "")

    async def unexpected(*args, **kwargs):
        pytest.fail("Missing key should not call Navitia")

    monkeypatch.setattr(main, "fetch_line_reports", unexpected)
    async with statistics_client as client:
        response = await client.get("/statistics")
    assert response.status_code == 503
