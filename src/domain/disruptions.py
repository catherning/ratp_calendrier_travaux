"""
Domain logic: disruption filtering, normalization, Pydantic models.
Core logic ported and cleaned from the original backend_app.py.
"""
import logging
import re
import unicodedata
from datetime import datetime, timedelta, time
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

# Common French stop words and qualifiers in station names
STOP_WORDS = {
    "sur", "sous", "la", "le", "les", "du", "des", "de", "et", "en", "au", "aux", "un", "une",
    "gare", "station", "rue", "avenue", "boulevard", "pont", "porte", "grand", "grande", "arche",
    "saint", "sainte", "val", "vieux", "vieille", "port", "pre", "pres", "maison", "maisons"
}


# ── Pydantic models ────────────────────────────────────────────────────────────

class DisruptionPeriod(BaseModel):
    """An individual date/time range of a disruption occurrence."""
    period_index: int
    date_debut: str        # ISO 8601
    date_fin: str          # ISO 8601


class DisruptionDetail(BaseModel):
    """A single disruption event, grouping all its active periods."""
    id: str               # Compound ID: "{impact_id}__p{earliest_period_index}"
    impact_id: str        # Navitia impact UUID
    period_index: int     # Earliest/active period index for backwards compatibility

    line_code: str        # e.g. "4", "A"
    line_navitia_id: str  # e.g. "C01374"
    line_name: str        # e.g. "Métro 4"
    line_color: str       # Hex without #, e.g. "C04191"
    line_text_color: str  # Hex without #, e.g. "FFFFFF"

    summary: str          # Short title suitable for calendar event
    date_debut: str       # ISO 8601 of earliest period
    date_fin: str         # ISO 8601 of latest period
    text: str             # Full human-readable description
    stations: str         # "toute la ligne" or "Station A | Station B"
    cause: str            # "travaux" | "perturbation" | ...
    effect: str           # Navitia severity effect
    impacts_itinerary: bool | None = None  # True if directly impacts search stops
    periods: list[DisruptionPeriod] = []


class ItinerarySection(BaseModel):
    """A segment of the calculated journey route."""
    type: str                  # "public_transport" | "street_network" | "waiting"
    mode: str | None = None       # "walking" | "metro" | "rer" | "train" | ...
    line_code: str | None = None  # e.g., "A", "4"
    line_color: str | None = None # e.g., "E3051C"
    line_text_color: str | None = None # e.g., "FFFFFF"
    from_name: str             # departure station
    to_name: str               # arrival station
    duration: int              # duration in seconds


class JourneyItinerary(BaseModel):
    """The complete calculated route proposed by Navitia."""
    duration: int              # total duration in seconds
    departure_time: str        # ISO timestamp
    arrival_time: str          # ISO timestamp
    sections: list[ItinerarySection]
    impacted_disruption_ids: list[str] = []


class JourneyDisruptionResponse(BaseModel):
    """Unified response containing the journey's itineraries and relevant disruptions."""
    itinerary: JourneyItinerary | None = None
    itineraries: list[JourneyItinerary] = []
    disruptions: list[DisruptionDetail]



# ── Helpers ────────────────────────────────────────────────────────────────────

def _navitia_dt_to_iso(navitia_dt: str) -> str:
    """
    Convert Navitia compact datetime to ISO 8601.
    '20260706T044500' → '2026-07-06T04:45:00'
    """
    s = navitia_dt.strip()
    if not s:
        return s

    if "-" in s:
        try:
            datetime.fromisoformat(s)
            return s
        except ValueError:
            pass

    try:
        clean_s = s.split(".")[0].replace("-", "").replace(":", "")
        dt = datetime.strptime(clean_s, "%Y%m%dT%H%M%S")
        return dt.isoformat()
    except Exception:
        try:
            if "T" in s:
                date_part, time_part = s.split("T", 1)
                date_part = date_part.replace("-", "")[:8]
                time_part = time_part.split(".")[0].replace(":", "")[:6]
                if len(date_part) == 8 and len(time_part) >= 6:
                    return (
                        f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
                        f"T{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
                    )
        except Exception:
            pass
        return s


def _apply_date_adjustments(date_debut_iso: str, date_fin_iso: str) -> str:
    """
    If the end date is on a later day than start date and ends in the morning (before 12:00 PM),
    shift it to 23:59:00 of the previous day so it doesn't overlap visually into the next day.
    """
    try:
        dt_debut = datetime.fromisoformat(date_debut_iso)
        dt_fin = datetime.fromisoformat(date_fin_iso)
        if dt_fin.date() > dt_debut.date() and dt_fin.hour < 12:
            prev_day_dt = datetime.combine(dt_fin.date() - timedelta(days=1), time(23, 59, 0))
            if prev_day_dt >= dt_debut:
                return prev_day_dt.isoformat()
    except Exception:
        pass
    return date_fin_iso


def _extract_message_by_channel(disruption: dict, channel_names: list[str]) -> str:
    messages = disruption.get("messages", [])
    for channel_name in channel_names:
        for msg in messages:
            if msg.get("channel", {}).get("name") == channel_name:
                raw = msg.get("text", "")
                if raw:
                    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return ""


def _extract_text(disruption: dict) -> str:
    """Extract the best detailed explanation text from a disruption's messages list."""
    detailed = _extract_message_by_channel(disruption, ["moteur"])
    if not detailed:
        detailed = _extract_message_by_channel(disruption, ["title", "notification", "titre", "cbiv"])
    if not detailed:
        messages = disruption.get("messages", [])
        if messages:
            detailed = BeautifulSoup(messages[0].get("text", ""), "html.parser").get_text(" ", strip=True)
    return detailed or "Travaux impactant le trafic"


def _extract_summary(disruption: dict) -> str:
    """Extract a short, crisp summary title."""
    summary = _extract_message_by_channel(disruption, ["title", "notification", "titre", "cbiv"])
    if not summary:
        detailed = _extract_text(disruption)
        summary = detailed[:60] if detailed else "Travaux"
    return summary


def _extract_stations(disruption: dict) -> str:
    """Return 'StationA | StationB' or a list of specific stations, or 'toute la ligne'."""
    stations = []

    for obj in disruption.get("impacted_objects", []):
        section = obj.get("impacted_section")
        if section:
            from_name = section.get("from", {}).get("name", "").split("(")[0].strip()
            to_name = section.get("to", {}).get("name", "").split("(")[0].strip()
            if from_name and from_name not in stations:
                stations.append(from_name)
            if to_name and to_name not in stations:
                stations.append(to_name)

    for obj in disruption.get("impacted_objects", []):
        pt = obj.get("pt_object", {})
        if pt:
            name = pt.get("name", "").split("(")[0].strip()
            if name and name not in stations:
                if not any(prefix in name for prefix in ["RER", "Métro", "Train", "Ligne"]):
                    stations.append(name)

    if stations:
        return " | ".join(stations)
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
    if cause == "perturbation":
        return False

    return True


def normalize_line_disruptions(raw: dict, line_info: LineInfo) -> list[DisruptionDetail]:
    """
    Convert a raw Navitia line_reports payload into a list of DisruptionDetail.
    Periods of the same disruption are grouped chronologically.
    """
    results: list[DisruptionDetail] = []

    for disruption in raw.get("disruptions", []):
        if not is_relevant_disruption(disruption):
            continue

        periods = disruption.get("application_periods", [])
        if not periods:
            continue

        parsed_periods = []
        for p_idx, period in enumerate(periods):
            begin = period.get("begin", "")
            end = period.get("end", "")
            try:
                date_debut = _navitia_dt_to_iso(begin)
                date_fin = _navitia_dt_to_iso(end)
                date_fin = _apply_date_adjustments(date_debut, date_fin)
                datetime.fromisoformat(date_debut)
                datetime.fromisoformat(date_fin)
                parsed_periods.append(DisruptionPeriod(
                    period_index=p_idx,
                    date_debut=date_debut,
                    date_fin=date_fin
                ))
            except Exception:
                logger.warning("Invalid period dates for disruption %s: %r / %r", disruption.get("id"), begin, end)
                continue

        if not parsed_periods:
            continue

        # Sort periods chronologically
        parsed_periods.sort(key=lambda p: p.date_debut)

        earliest_p = parsed_periods[0]
        latest_p = parsed_periods[-1]

        detailed_text = _extract_text(disruption)
        short_summary = _extract_summary(disruption)
        stations = _extract_stations(disruption)
        impact_id = disruption.get("impact_id") or disruption.get("id", "")

        clean_title = short_summary.replace("/", "-").replace("|", "-")
        summary = f"Ligne {line_info.code} — {clean_title}"

        results.append(DisruptionDetail(
            id=f"{impact_id}__p{earliest_p.period_index}",
            impact_id=impact_id,
            period_index=earliest_p.period_index,
            line_code=line_info.code,
            line_navitia_id=line_info.navitia_id,
            line_name=line_info.name,
            line_color=line_info.color,
            line_text_color=line_info.text_color,
            summary=summary,
            date_debut=earliest_p.date_debut,
            date_fin=latest_p.date_fin,  # End date of the latest period for correct filtering
            text=detailed_text,
            stations=stations,
            cause=disruption.get("cause", ""),
            effect=disruption.get("severity", {}).get("effect", ""),
            periods=parsed_periods
        ))

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
        
        # Build a single-period DisruptionDetail
        p = periods[period_index]
        begin = p.get("begin", "")
        end = p.get("end", "")
        try:
            date_debut = _navitia_dt_to_iso(begin)
            date_fin = _navitia_dt_to_iso(end)
            date_fin = _apply_date_adjustments(date_debut, date_fin)
        except Exception:
            continue

        detailed_text = _extract_text(disruption)
        short_summary = _extract_summary(disruption)
        stations = _extract_stations(disruption)

        clean_title = short_summary.replace("/", "-").replace("|", "-")
        summary = f"Ligne {line_info.code} — {clean_title}"

        return DisruptionDetail(
            id=f"{impact_id}__p{period_index}",
            impact_id=impact_id,
            period_index=period_index,
            line_code=line_info.code,
            line_navitia_id=line_info.navitia_id,
            line_name=line_info.name,
            line_color=line_info.color,
            line_text_color=line_info.text_color,
            summary=summary,
            date_debut=date_debut,
            date_fin=date_fin,
            text=detailed_text,
            stations=stations,
            cause=disruption.get("cause", ""),
            effect=disruption.get("severity", {}).get("effect", ""),
            periods=[DisruptionPeriod(period_index=period_index, date_debut=date_debut, date_fin=date_fin)]
        )
    return None


def find_disruption_detail_with_all_periods(
    raw: dict,
    impact_id: str,
    line_info: LineInfo,
) -> DisruptionDetail | None:
    """Look up a disruption by impact_id and return it with all its periods populated."""
    for disruption in raw.get("disruptions", []):
        d_impact_id = disruption.get("impact_id") or disruption.get("id", "")
        if d_impact_id != impact_id:
            continue
        
        periods = disruption.get("application_periods", [])
        if not periods:
            return None
            
        parsed_periods = []
        for p_idx, p in enumerate(periods):
            begin = p.get("begin", "")
            end = p.get("end", "")
            try:
                date_debut = _navitia_dt_to_iso(begin)
                date_fin = _navitia_dt_to_iso(end)
                date_fin = _apply_date_adjustments(date_debut, date_fin)
                datetime.fromisoformat(date_debut)
                datetime.fromisoformat(date_fin)
                parsed_periods.append(DisruptionPeriod(
                    period_index=p_idx,
                    date_debut=date_debut,
                    date_fin=date_fin
                ))
            except Exception:
                continue
                
        if not parsed_periods:
            return None
            
        parsed_periods.sort(key=lambda p: p.date_debut)
        earliest_p = parsed_periods[0]
        latest_p = parsed_periods[-1]
        
        detailed_text = _extract_text(disruption)
        short_summary = _extract_summary(disruption)
        stations = _extract_stations(disruption)
        
        clean_title = short_summary.replace("/", "-").replace("|", "-")
        summary = f"Ligne {line_info.code} — {clean_title}"
        
        return DisruptionDetail(
            id=f"{impact_id}__p{earliest_p.period_index}",
            impact_id=impact_id,
            period_index=earliest_p.period_index,
            line_code=line_info.code,
            line_navitia_id=line_info.navitia_id,
            line_name=line_info.name,
            line_color=line_info.color,
            line_text_color=line_info.text_color,
            summary=summary,
            date_debut=earliest_p.date_debut,
            date_fin=latest_p.date_fin,
            text=detailed_text,
            stations=stations,
            cause=disruption.get("cause", ""),
            effect=disruption.get("severity", {}).get("effect", ""),
            periods=parsed_periods
        )
    return None


def _normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = name.replace("-", " ").replace("œ", "oe")
    return " ".join(name.split())


def filter_for_journey(
    disruptions: list[DisruptionDetail],
    journey_stops: list[dict],
) -> list[DisruptionDetail]:
    """
    Filter disruptions to return only those that impact the journey's stops.
    Uses exact station matches first, then applies a robust text-analysis keyword
    matching heuristic to filter out branch-specific disruptions (such as Western Cergy/Poissy
    works for Eastern République/Nogent travelers).
    """
    # Clean and normalize journey stop names
    journey_stop_names = {_normalize_name(s["name"]) for s in journey_stops if s.get("name")}
    
    # Extract significant words from the journey stops
    significant_journey_words = set()
    for name in journey_stop_names:
        words = name.split()
        for w in words:
            if len(w) >= 3 and w not in STOP_WORDS:
                significant_journey_words.add(w)

    filtered = []
    for d in disruptions:
        # 1. If stations are explicitly specified and not "toute la ligne", use exact station matching
        if d.stations != "toute la ligne":
            disrupted_stations = [_normalize_name(s) for s in d.stations.split(" | ")]
            if any(ds in journey_stop_names for ds in disrupted_stations):
                filtered.append(d)
                continue
                
            # Fallback to keyword matching on explicit stations to handle minor spelling or punctuation differences
            disrupted_words = set()
            for ds in disrupted_stations:
                for w in ds.split():
                    if len(w) >= 3 and w not in STOP_WORDS:
                        disrupted_words.add(w)
            if disrupted_words & significant_journey_words:
                filtered.append(d)
                continue
                
            continue

        # 2. If stations is "toute la ligne", inspect the text/summary for localized indicators.
        text_lower = _normalize_name(d.text + " " + d.summary)
        
        # Localized indicators in French
        localized_indicators = [
            "entre", "interrompu", "interruption", "fermeture", "ferme", "fermee", 
            "travaux a", "uniquement", "non desservi", "non desservie", "sauf"
        ]
        
        is_localized = any(indicator in text_lower for indicator in localized_indicators)
        
        if not is_localized:
            # If there's no localized indicator, assume it's a line-wide disruption (strike, general delay, etc.)
            filtered.append(d)
            continue
            
        # If it is localized, check if any of our journey's significant words appear in the description
        # We also allow general line-wide indicators in the text
        line_wide_indicators = ["ensemble de la ligne", "toute la ligne", "toutes les gares", "toutes les stations"]
        if any(lw in text_lower for lw in line_wide_indicators):
            filtered.append(d)
            continue
            
        # Match using exact word boundaries
        has_matching_station = False
        for word in significant_journey_words:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_lower):
                has_matching_station = True
                break
                
        if has_matching_station:
            filtered.append(d)
        else:
            # Localized disruption on another branch of the line — does not impact!
            logger.debug(
                "Disruption %s (%s) ignored for journey stops %s (no matching words in text)", 
                d.id, d.summary, list(journey_stop_names)
            )

    return filtered
