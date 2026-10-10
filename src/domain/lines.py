"""Validated line metadata, loaded once from the packaged JSON catalogue."""
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError
from pydantic.dataclasses import dataclass


@dataclass(frozen=True, config=ConfigDict(extra="forbid"))
class LineInfo:
    navitia_id: Annotated[str, Field(pattern=r"^C[0-9]{5}$")]
    code: Annotated[str, Field(min_length=1, pattern=r"^\S+$")]
    name: Annotated[str, Field(min_length=1)]
    mode: Literal["metro", "rer", "transilien"]
    color: Annotated[str, Field(pattern=r"^[0-9A-Fa-f]{6}$")]
    text_color: Annotated[str, Field(pattern=r"^[0-9A-Fa-f]{6}$")]
    logo_url: Annotated[str, Field(pattern=r"^https://\S+$")]


LINE_METADATA_PATH = Path(__file__).with_name("lines.json")


def load_line_registry(path: Path = LINE_METADATA_PATH) -> dict[str, LineInfo]:
    """Fail explicitly on a missing/invalid catalogue instead of hiding lines."""
    try:
        lines = TypeAdapter(list[LineInfo]).validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"Unable to load line catalogue {path}: {exc}") from exc
    if not lines:
        raise ValueError(f"Empty line catalogue: {path}")

    registry: dict[str, LineInfo] = {}
    navitia_ids: set[str] = set()
    for line in lines:
        if line.code in registry:
            raise ValueError(f"Duplicate line code {line.code} in {path}")
        if line.navitia_id in navitia_ids:
            raise ValueError(f"Duplicate Navitia ID {line.navitia_id} in {path}")
        registry[line.code] = line
        navitia_ids.add(line.navitia_id)
    return registry


LINE_REGISTRY = load_line_registry()

# Catalogue order is the display order; no separately maintained code lists.
ALL_CODES = list(LINE_REGISTRY)
METRO_CODES = [code for code, line in LINE_REGISTRY.items() if line.mode == "metro"]
RER_CODES = [code for code, line in LINE_REGISTRY.items() if line.mode == "rer"]
TRANSILIEN_CODES = [code for code, line in LINE_REGISTRY.items() if line.mode == "transilien"]


def get_line(code: str) -> LineInfo | None:
    return LINE_REGISTRY.get(code)
