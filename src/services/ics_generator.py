"""
ICS file generation and Google Calendar URL builder.
Works entirely from DisruptionDetail data — no Navitia calls needed.
"""
import uuid
from datetime import datetime, timezone

from icalendar import Calendar, Event

DATE_FORMAT = "%Y%m%dT%H%M%S"


def _parse_iso(iso_str: str) -> datetime:
    """Parse ISO 8601 string like '2025-07-06T04:45:00' to a naive datetime."""
    return datetime.fromisoformat(iso_str)


def build_ics_bytes(
    summary: str,
    date_debut: str,
    date_fin: str,
    description: str = "",
    location: str = "",
) -> bytes:
    """
    Build an ICS file (RFC 5545) as raw bytes for the given event.

    Args:
        summary: Calendar event title.
        date_debut: ISO 8601 start datetime.
        date_fin: ISO 8601 end datetime.
        description: Optional long description.
        location: Optional station info.

    Returns:
        Bytes of the .ics file.
    """
    cal = Calendar()
    cal.add("prodid", "-//RATP Travaux//FR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    event = Event()
    event.add("summary", summary)
    event.add("dtstart", _parse_iso(date_debut))
    event.add("dtend", _parse_iso(date_fin))
    event.add("uid", str(uuid.uuid4()))
    event.add("dtstamp", datetime.now(timezone.utc))

    if description:
        event.add("description", description)
    if location:
        event.add("location", location)

    cal.add_component(event)
    return cal.to_ical()


def build_google_calendar_url(
    summary: str,
    date_debut: str,
    date_fin: str,
    description: str = "",
) -> str:
    """
    Build a Google Calendar 'add event' URL.

    Args:
        summary: Event title.
        date_debut: ISO 8601 start datetime.
        date_fin: ISO 8601 end datetime.
        description: Optional details text.

    Returns:
        A fully formed calendar.google.com URL string.
    """
    def to_gc(iso_str: str) -> str:
        return _parse_iso(iso_str).strftime(DATE_FORMAT)

    title = summary.replace(" ", "+").replace("—", "-")
    dates = f"{to_gc(date_debut)}/{to_gc(date_fin)}"

    url = (
        "https://calendar.google.com/calendar/render"
        f"?action=TEMPLATE&text={title}&dates={dates}&ctz=Europe/Paris"
    )

    if description:
        # Cap description length for URL safety
        safe_desc = description[:400].replace(" ", "+").replace("&", "%26")
        url += f"&details={safe_desc}"

    return url


def build_bulk_ics_bytes(disruptions: list) -> bytes:
    """
    Build a single ICS file containing multiple disruption events.
    """
    cal = Calendar()
    cal.add("prodid", "-//RATP Travaux Bulk//FR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    for d in disruptions:
        event = Event()
        event.add("summary", d.summary)
        event.add("dtstart", _parse_iso(d.date_debut))
        event.add("dtend", _parse_iso(d.date_fin))
        event.add("uid", str(uuid.uuid4()))
        event.add("dtstamp", datetime.now(timezone.utc))

        if d.text:
            event.add("description", d.text)
        if d.stations and d.stations != "toute la ligne":
            event.add("location", d.stations)

        cal.add_component(event)

    return cal.to_ical()

