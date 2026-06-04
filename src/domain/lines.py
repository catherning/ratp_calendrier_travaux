"""
Line registry for all Métro, RER and Transilien lines.
Navitia IDs confirmed from live API responses.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LineInfo:
    navitia_id: str     # IDFM short code, e.g. "C01374"
    code: str           # Display code, e.g. "4", "A", "H"
    name: str           # Full display name, e.g. "Métro 4"
    mode: str           # "metro" | "rer" | "transilien"
    color: str          # Hex without #, e.g. "C04191"
    text_color: str     # Hex without #, e.g. "FFFFFF"
    logo_url: str


_WIKI = "https://upload.wikimedia.org/wikipedia/commons/thumb"
_WIKI_FULL = "https://upload.wikimedia.org/wikipedia/commons"

LINE_REGISTRY: dict[str, LineInfo] = {
    # ── Métro ──────────────────────────────────────────────────────────────
    "1": LineInfo(
        "C01371", "1", "Métro 1", "metro", "FFCE00", "000000",
        f"{_WIKI}/3/30/Paris_transit_icons_-_M%C3%A9tro_1.svg/120px-Paris_transit_icons_-_M%C3%A9tro_1.svg.png",
    ),
    "2": LineInfo(
        "C01372", "2", "Métro 2", "metro", "0064B0", "FFFFFF",
        f"{_WIKI}/d/da/Paris_transit_icons_-_M%C3%A9tro_2.svg/120px-Paris_transit_icons_-_M%C3%A9tro_2.svg.png",
    ),
    "3": LineInfo(
        "C01373", "3", "Métro 3", "metro", "9F9825", "FFFFFF",
        f"{_WIKI}/0/01/Paris_transit_icons_-_M%C3%A9tro_3.svg/120px-Paris_transit_icons_-_M%C3%A9tro_3.svg.png",
    ),
    "4": LineInfo(
        "C01374", "4", "Métro 4", "metro", "C04191", "FFFFFF",
        f"{_WIKI}/7/76/Paris_transit_icons_-_M%C3%A9tro_4.svg/120px-Paris_transit_icons_-_M%C3%A9tro_4.svg.png",
    ),
    "5": LineInfo(
        "C01375", "5", "Métro 5", "metro", "F28E42", "000000",
        f"{_WIKI}/5/54/Paris_transit_icons_-_M%C3%A9tro_5.svg/120px-Paris_transit_icons_-_M%C3%A9tro_5.svg.png",
    ),
    "6": LineInfo(
        "C01376", "6", "Métro 6", "metro", "83C491", "000000",
        f"{_WIKI}/6/6f/Paris_transit_icons_-_M%C3%A9tro_6.svg/120px-Paris_transit_icons_-_M%C3%A9tro_6.svg.png",
    ),
    "7": LineInfo(
        "C01377", "7", "Métro 7", "metro", "F3A4BA", "000000",
        f"{_WIKI}/2/21/Paris_transit_icons_-_M%C3%A9tro_7.svg/120px-Paris_transit_icons_-_M%C3%A9tro_7.svg.png",
    ),
    "8": LineInfo(
        "C01378", "8", "Métro 8", "metro", "CEADD2", "000000",
        f"{_WIKI}/e/e8/Paris_transit_icons_-_M%C3%A9tro_8.svg/120px-Paris_transit_icons_-_M%C3%A9tro_8.svg.png",
    ),
    "9": LineInfo(
        "C01379", "9", "Métro 9", "metro", "D5C900", "000000",
        f"{_WIKI}/1/10/Paris_transit_icons_-_M%C3%A9tro_9.svg/120px-Paris_transit_icons_-_M%C3%A9tro_9.svg.png",
    ),
    "10": LineInfo(
        "C01380", "10", "Métro 10", "metro", "E3B32A", "000000",
        f"{_WIKI}/2/24/Paris_transit_icons_-_M%C3%A9tro_10.svg/120px-Paris_transit_icons_-_M%C3%A9tro_10.svg.png",
    ),
    "11": LineInfo(
        "C01381", "11", "Métro 11", "metro", "8D5E2A", "FFFFFF",
        f"{_WIKI}/c/c1/Paris_transit_icons_-_M%C3%A9tro_11.svg/120px-Paris_transit_icons_-_M%C3%A9tro_11.svg.png",
    ),
    "12": LineInfo(
        "C01382", "12", "Métro 12", "metro", "00814F", "FFFFFF",
        f"{_WIKI}/3/3f/Paris_transit_icons_-_M%C3%A9tro_12.svg/120px-Paris_transit_icons_-_M%C3%A9tro_12.svg.png",
    ),
    "13": LineInfo(
        "C01383", "13", "Métro 13", "metro", "98D4E2", "000000",
        f"{_WIKI}/a/a9/Paris_transit_icons_-_M%C3%A9tro_13.svg/120px-Paris_transit_icons_-_M%C3%A9tro_13.svg.png",
    ),
    "14": LineInfo(
        "C01384", "14", "Métro 14", "metro", "662483", "FFFFFF",
        f"{_WIKI}/9/93/Paris_transit_icons_-_M%C3%A9tro_14.svg/120px-Paris_transit_icons_-_M%C3%A9tro_14.svg.png",
    ),
    "15": LineInfo(
        "C01529", "15", "Métro 15", "metro", "B90845", "FFFFFF",
        f"{_WIKI}/5/55/Paris_transit_icons_-_M%C3%A9tro_15.svg/120px-Paris_transit_icons_-_M%C3%A9tro_15.svg.png",
    ),
    # ── RER ────────────────────────────────────────────────────────────────
    "A": LineInfo(
        "C01742", "A", "RER A", "rer", "E3051C", "FFFFFF",
        f"{_WIKI_FULL}/4/4a/Paris_transit_icons_-_RER_A.svg",
    ),
    "B": LineInfo(
        "C01743", "B", "RER B", "rer", "5291CE", "FFFFFF",
        f"{_WIKI_FULL}/f/fd/Paris_transit_icons_-_RER_B.svg",
    ),
    "C": LineInfo(
        "C01728", "C", "RER C", "rer", "FFEA00", "000000",
        f"{_WIKI_FULL}/e/e4/Paris_transit_icons_-_RER_C.svg",
    ),
    "D": LineInfo(
        "C01729", "D", "RER D", "rer", "00A06E", "FFFFFF",
        f"{_WIKI_FULL}/4/4d/Paris_transit_icons_-_RER_D.svg",
    ),
    "E": LineInfo(
        "C01740", "E", "RER E", "rer", "B93684", "FFFFFF",
        f"{_WIKI_FULL}/2/25/Paris_transit_icons_-_RER_E.svg",
    ),
    # ── Transilien ─────────────────────────────────────────────────────────
    # TODO: verify navitia_ids for Transilien lines via API
    "H": LineInfo(
        "C01570", "H", "Transilien H", "transilien", "6E6E00", "FFFFFF",
        f"{_WIKI_FULL}/d/d6/Paris_transit_icons_-_Train_H.svg",
    ),
    "J": LineInfo(
        "C01571", "J", "Transilien J", "transilien", "C9A71C", "FFFFFF",
        f"{_WIKI_FULL}/a/a5/Paris_transit_icons_-_Train_J.svg",
    ),
    "K": LineInfo(
        "C01572", "K", "Transilien K", "transilien", "9F9825", "FFFFFF",
        f"{_WIKI_FULL}/5/58/Paris_transit_icons_-_Train_K.svg",
    ),
    "L": LineInfo(
        "C01573", "L", "Transilien L", "transilien", "8DB7C8", "000000",
        f"{_WIKI_FULL}/b/b9/Paris_transit_icons_-_Train_L.svg",
    ),
    "N": LineInfo(
        "C01574", "N", "Transilien N", "transilien", "004899", "FFFFFF",
        f"{_WIKI_FULL}/f/f0/Paris_transit_icons_-_Train_N.svg",
    ),
    "P": LineInfo(
        "C01575", "P", "Transilien P", "transilien", "F0A500", "FFFFFF",
        f"{_WIKI_FULL}/4/41/Paris_transit_icons_-_Train_P.svg",
    ),
    "R": LineInfo(
        "C01576", "R", "Transilien R", "transilien", "E87B10", "FFFFFF",
        f"{_WIKI_FULL}/6/69/Paris_transit_icons_-_Train_R.svg",
    ),
    "U": LineInfo(
        "C01577", "U", "Transilien U", "transilien", "CE007C", "FFFFFF",
        f"{_WIKI_FULL}/9/9d/Paris_transit_icons_-_Train_U.svg",
    ),
}

# Ordered list for frontend display
METRO_CODES = [str(i) for i in range(1, 16)]
RER_CODES = ["A", "B", "C", "D", "E"]
TRANSILIEN_CODES = ["H", "J", "K", "L", "N", "P", "R", "U"]
ALL_CODES = METRO_CODES + RER_CODES + TRANSILIEN_CODES


def get_line(code: str) -> LineInfo | None:
    return LINE_REGISTRY.get(code)


def get_line_by_navitia_id(navitia_id: str) -> LineInfo | None:
    """Look up a LineInfo by its short navitia ID (e.g. 'C01374')."""
    for info in LINE_REGISTRY.values():
        if info.navitia_id == navitia_id:
            return info
    return None


def navitia_full_id(code: str) -> str:
    """Return the full Navitia line ID, e.g. 'line:IDFM:C01374'."""
    info = LINE_REGISTRY[code]
    return f"line:IDFM:{info.navitia_id}"
