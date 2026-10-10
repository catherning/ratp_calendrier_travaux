import os
import time
from datetime import datetime, timezone
import pytest
from src.domain.disruptions import normalize_line_disruptions
from src.domain.lines import LINE_REGISTRY
from src.services.ics_generator import (
    build_ics_bytes,
    build_google_calendar_url,
    build_bulk_ics_bytes,
)
from src.services.navitia_client import (
    _cache_get,
    _cache_set,
    fetch_line_reports,
    fetch_places,
)


class MockDisruption:
    def __init__(self, summary, date_debut, date_fin, text, stations):
        self.summary = summary
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.text = text
        self.stations = stations


def test_navitia_client_cache_mechanism():
    """Verify that in-process cache gets, sets, and evicts correctly."""
    mock_cache = {}
    key = "C01742"
    payload = {"test": "data"}
    ttl = 1.0  # 1 second

    # Set cache entry
    _cache_set(mock_cache, key, payload, ttl)
    assert key in mock_cache

    # Retrieve valid entry
    data = _cache_get(mock_cache, key)
    assert data == payload

    # Retrieve expired entry
    time.sleep(1.1)
    expired_data = _cache_get(mock_cache, key)
    assert expired_data is None


def test_build_ics_bytes():
    """Verify that the generated ICS bytes match RFC-5545 specifications."""
    summary = "Travaux RER A"
    date_debut = "2026-07-25T04:45:00"
    date_fin = "2026-07-25T23:59:59"
    description = "Interruption de Vincennes à Noisy-le-Grand"
    location = "Vincennes | Noisy-le-Grand"

    ics_bytes = build_ics_bytes(
        summary=summary,
        date_debut=date_debut,
        date_fin=date_fin,
        description=description,
        location=location,
    )

    assert isinstance(ics_bytes, bytes)
    ics_text = ics_bytes.decode("utf-8")

    # Check key iCalendar fields
    assert "BEGIN:VCALENDAR" in ics_text
    assert "PRODID:-//RATP Travaux//FR" in ics_text
    assert "VERSION:2.0" in ics_text
    assert "BEGIN:VEVENT" in ics_text
    assert f"SUMMARY:{summary}" in ics_text
    assert "DTSTART:20260725T044500" in ics_text
    assert "DTEND:20260725T235959" in ics_text
    assert "DESCRIPTION" in ics_text
    assert "LOCATION:Vincennes | Noisy-le-Grand" in ics_text
    assert "END:VEVENT" in ics_text
    assert "END:VCALENDAR" in ics_text


def test_build_google_calendar_url():
    """Verify Google Calendar URL template deep link structure."""
    summary = "Travaux Ligne 8"
    date_debut = "2026-07-25T04:00:00"
    date_fin = "2026-07-25T22:00:00"
    description = "Service réduit"

    url = build_google_calendar_url(
        summary=summary,
        date_debut=date_debut,
        date_fin=date_fin,
        description=description,
    )

    assert "https://calendar.google.com/calendar/render" in url
    assert "action=TEMPLATE" in url
    assert "text=Travaux+Ligne+8" in url
    assert "dates=20260725T040000%2F20260725T220000" in url
    assert "details=Service+r%C3%A9duit" in url
    assert "ctz=Europe%2FParis" in url


def test_build_bulk_ics_bytes():
    """Verify aggregated ICS generation contains all disruption events."""
    disruptions = [
        MockDisruption(
            summary="Travaux Ligne 1",
            date_debut="2026-07-25T05:00:00",
            date_fin="2026-07-25T23:00:00",
            text="Trafic interrompu",
            stations="Nation | Bastille",
        ),
        MockDisruption(
            summary="Travaux Ligne 2",
            date_debut="2026-07-26T06:00:00",
            date_fin="2026-07-26T22:00:00",
            text="Service réduit",
            stations="Anvers | Pigalle",
        ),
    ]

    bulk_bytes = build_bulk_ics_bytes(disruptions)
    assert isinstance(bulk_bytes, bytes)
    bulk_text = bulk_bytes.decode("utf-8")

    assert "PRODID:-//RATP Travaux Bulk//FR" in bulk_text
    assert "SUMMARY:Travaux Ligne 1" in bulk_text
    assert "SUMMARY:Travaux Ligne 2" in bulk_text
    assert "LOCATION:Nation | Bastille" in bulk_text
    assert "LOCATION:Anvers | Pigalle" in bulk_text
    assert bulk_text.count("BEGIN:VEVENT") == 2


@pytest.mark.skipif(not os.getenv("NAVITIA_API_KEY"), reason="NAVITIA_API_KEY not configured")
@pytest.mark.asyncio
async def test_navitia_line_reports_smoke():
    """Smoke test: a known-good line should return a valid payload shape from Navitia."""
    data = await fetch_line_reports("C01374", os.environ["NAVITIA_API_KEY"])
    assert isinstance(data, dict)
    disruptions = data.get("disruptions", [])
    assert isinstance(disruptions, list)
    if disruptions:
        assert "id" in disruptions[0] or "impact_id" in disruptions[0]


@pytest.mark.skipif(not os.getenv("NAVITIA_API_KEY"), reason="NAVITIA_API_KEY not configured")
@pytest.mark.asyncio
async def test_navitia_places_smoke():
    """Smoke test: a known search term should resolve to one or more stop areas."""
    places = await fetch_places("Nation", os.environ["NAVITIA_API_KEY"], count=5)
    assert isinstance(places, list)
    if places:
        first = places[0]
        assert isinstance(first, dict)
        assert "id" in first or "stop_area" in first


def test_normalize_line_disruptions_filters_and_groups_periods():
    """Verify raw Navitia payloads are normalized into grouped disruption objects."""
    raw = {
        "disruptions": [
            {
                "id": "impact-valid",
                "impact_id": "impact-valid",
                "cause": "travaux",
                "severity": {"effect": "REDUCED_SERVICE"},
                "tags": ["maintenance"],
                "messages": [
                    {"channel": {"name": "title"}, "text": "Travaux sur la ligne"},
                    {"channel": {"name": "moteur"}, "text": "<p>Travaux entre Nation et Bastille.</p>"},
                ],
                "application_periods": [
                    {"begin": "2026-07-25T04:45:00", "end": "2026-07-25T23:59:00"},
                    {"begin": "2026-07-26T04:45:00", "end": "2026-07-26T23:59:00"},
                ],
                "impacted_objects": [
                    {"impacted_section": {"from": {"name": "Nation"}, "to": {"name": "Bastille"}}}
                ],
            },
            {
                "id": "impact-ignored",
                "impact_id": "impact-ignored",
                "cause": "travaux",
                "severity": {"effect": "REDUCED_SERVICE"},
                "tags": ["ascenseur"],
                "messages": [{"channel": {"name": "title"}, "text": "Should be ignored"}],
                "application_periods": [{"begin": "2026-07-27T04:45:00", "end": "2026-07-27T23:59:00"}],
            },
        ]
    }

    normalized = normalize_line_disruptions(raw, LINE_REGISTRY["A"])

    assert len(normalized) == 1
    disruption = normalized[0]
    assert disruption.line_code == "A"
    assert disruption.summary.startswith("Ligne A —")
    assert "Travaux" in disruption.summary
    assert disruption.stations == "Nation | Bastille"
    assert disruption.date_debut == "2026-07-25T04:45:00"
    assert disruption.date_fin == "2026-07-26T23:59:00"
    assert len(disruption.periods) == 2
    assert [p.period_index for p in disruption.periods] == [0, 1]
