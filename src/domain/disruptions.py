"""
Domain logic: disruption filtering, normalization, Pydantic models.
Core logic ported and cleaned from the original backend_app.py.
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup
from pydantic import BaseModel

from src.domain.lines import LineInfo

logger = logging.getLogger(__name__)

# Effects that are operationally impactful enough to display
IMPACTING_EFFECTS = {
    "NO_SERVICE",
    "SIGNIFICANT_DELAYS",
    "REDUCED_SERVICE",
    "DETOUR",
    "MODIFIED_SERVICE",
}

# Tags that indicate non-construction disruptions to ignore
IGNORED_TAGS = {"ascenseur"}


# ── Pydantic model ─────────────────────────────────────────────────────────────

class DisruptionDetail(BaseModel):
    """A single disruption event (one application_period of a Navitia disruption)."""
    id: str               # Compound: "{impact_id}__p{period_index}"
    impact_id: str        # Navitia impact UUID
    period_index: int     # Which application_period this represents

    line_code: str        # e.g. "4", "A"
    line_navitia_id: str  # e.g. "C01374"
    line_name: str        # e.g. "Métro 4"
    line_color: str       # Hex without #, e.g. "C04191"
    line_text_color: str  # Hex without #, e.g. "FFFFFF"

    summary: str          # Short title suitable for calendar event
    date_debut: str       # ISO 8601: "2025-07-06T04:45:00"
    date_fin: str         # ISO 8601: "2025-07-25T04:30:00"
    text: str             # Full human-readable description
    stations: str         # "toute la ligne" or "Station A | Station B"
    cause: str            # "travaux" | "perturbation" | ...
    effect: str           # Navitia severity effect


# ── Helpers ────────────────────────────────────────────────────────────────────

def _navitia_dt_to_iso(navitia_dt: str) -> str:
    """
    Convert Navitia compact datetime to ISO 8601.
    '20260706T044500' → '2026-07-06T04:45:00'
    Also handles '20260706T044500.000' variants.
    """
    s = navitia_dt.strip()
    if "T" not in s:
        return s
    date_part, time_part = s.split("T", 1)
    date_part = date_part.replace("-", "")[:8]
    time_part = time_part.split(".")[0].replace(":", "")[:6]
    return (
        f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
        f"T{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
    )


def _extract_text(disruption: dict) -> str:
    """Extract the best human-readable text from a disruption's messages list."""
    messages = disruption.get("messages", [])
    if not messages:
        return ""
    preferred_channels = ["title", "notification", "moteur"]
    for channel_name in preferred_channels:
        for msg in messages:
            if msg.get("channel", {}).get("name") == channel_name:
                raw = msg.get("text", "")
                return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return BeautifulSoup(messages[0].get("text", ""), "html.parser").get_text(" ", strip=True)


def _extract_stations(disruption: dict) -> str:
    """Return 'StationA | StationB' or 'toute la ligne'."""
    for obj in disruption.get("impacted_objects", []):
        section = obj.get("impacted_section")
        if not section:
            continue
        from_name = section.get("from", {}).get("name", "").split("(")[0].strip()
        to_name = section.get("to", {}).get("name", "").split("(")[0].strip()
        if from_name and to_name and from_name != to_name:
            return f"{from_name} | {to_name}"
    return "toute la ligne"


# ── Public API ─────────────────────────────────────────────────────────────────

def is_relevant_disruption(disruption: dict) -> bool:
    """Return True if this disruption is worth showing to the user."""
    tags = [tag.lower() for tag in disruption.get("tags", [])]
    if any(tag in IGNORED_TAGS for tag in tags):
        return False

    effect = disruption.get("severity", {}).get("effect", "")
    if effect not in IMPACTING_EFFECTS:
        return False

    cause = disruption.get("cause", "")
    # "perturbation" (accidents, strikes, demonstrations) is not construction work
    if cause == "perturbation":
        return False

    return True


def _period_to_detail(
    disruption: dict,
    period: dict,
    period_idx: int,
    line_info: LineInfo,
) -> DisruptionDetail | None:
    """Convert one application_period of a disruption to a DisruptionDetail."""
    begin = period.get("begin", "")
    end = period.get("end", "")

    try:
        date_debut = _navitia_dt_to_iso(begin)
        date_fin = _navitia_dt_to_iso(end)
        datetime.fromisoformat(date_debut)
        datetime.fromisoformat(date_fin)
    except (ValueError, IndexError, AttributeError):
        logger.warning("Invalid period dates for disruption %s: %r / %r", disruption.get("id"), begin, end)
        return None

    text = _extract_text(disruption)
    if not text:
        text = "Travaux impactant le trafic"

    stations = _extract_stations(disruption)
    impact_id = disruption.get("impact_id") or disruption.get("id", "")

    # Title: strip to 110 chars and sanitise forbidden chars
    title = text[:110].replace("/", "-").replace("|", "-")
    summary = f"Ligne {line_info.code} — {title}"

    return DisruptionDetail(
        id=f"{impact_id}__p{period_idx}",
        impact_id=impact_id,
        period_index=period_idx,
        line_code=line_info.code,
        line_navitia_id=line_info.navitia_id,
        line_name=line_info.name,
        line_color=line_info.color,
        line_text_color=line_info.text_color,
        summary=summary,
        date_debut=date_debut,
        date_fin=date_fin,
        text=text,
        stations=stations,
        cause=disruption.get("cause", ""),
        effect=disruption.get("severity", {}).get("effect", ""),
    )


def normalize_line_disruptions(raw: dict, line_info: LineInfo) -> list[DisruptionDetail]:
    """
    Convert a raw Navitia line_reports payload into a flat list of DisruptionDetail,
    one entry per relevant disruption × application_period.
    """
    results: list[DisruptionDetail] = []

    for disruption in raw.get("disruptions", []):
        if not is_relevant_disruption(disruption):
            continue

        periods = disruption.get("application_periods", [])
        if not periods:
            continue

        for p_idx, period in enumerate(periods):
            detail = _period_to_detail(disruption, period, p_idx, line_info)
            if detail:
                results.append(detail)

    return results


def find_disruption_in_raw(
    raw: dict,
    impact_id: str,
    period_index: int,
    line_info: LineInfo,
) -> DisruptionDetail | None:
    """Look up a specific (impact_id, period_index) from a cached raw payload."""
    for disruption in raw.get("disruptions", []):
        d_impact_id = disruption.get("impact_id") or disruption.get("id", "")
        if d_impact_id != impact_id:
            continue
        periods = disruption.get("application_periods", [])
        if period_index >= len(periods):
            return None
        return _period_to_detail(disruption, periods[period_index], period_index, line_info)
    return None


def _normalize_name(name: str) -> str:
    import unicodedata
    name = name.lower().strip()
    # Remove accents
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    # Replace dashes and other spacers with simple spaces
    name = name.replace("-", " ").replace("œ", "oe")
    return " ".join(name.split())


def filter_for_journey(
    disruptions: list[DisruptionDetail],
    journey_stops: list[dict],
) -> list[DisruptionDetail]:
    """
    Filter disruptions to return only those that impact the journey's stops.
    Each element in journey_stops has 'id' (stop point id) and 'name' (stop name).
    """
    journey_stop_names = {_normalize_name(s["name"]) for s in journey_stops if s.get("name")}

    filtered = []
    for d in disruptions:
        # 1. Entire line disruptions are always relevant
        if d.stations == "toute la ligne":
            filtered.append(d)
            continue

        # 2. Section disruptions (e.g. "Station A | Station B")
        # Split by " | " and check if any station is in our journey
        disrupted_stations = [_normalize_name(s) for s in d.stations.split(" | ")]
        if any(ds in journey_stop_names for ds in disrupted_stations):
            filtered.append(d)
            continue

    return filtered

