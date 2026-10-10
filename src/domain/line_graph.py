"""Station adjacency from ordered Navitia base-schedule stop times."""
import math
from typing import TypedDict


class GraphStation(TypedDict):
    name: str
    lat: float
    lon: float
    neighbors: list[str]


class LineGraph(TypedDict):
    stations: dict[str, GraphStation]


class LineGraphBuilder:
    def __init__(self) -> None:
        self.stations: dict[str, GraphStation] = {}
        self.paths: set[tuple[str, ...]] = set()

    def add_journey(self, journey: dict) -> None:
        stop_times = journey.get("stop_times")
        if not isinstance(stop_times, list) or not stop_times:
            raise ValueError("Vehicle journey has no ordered stop_times")
        path: list[str] = []
        for stop_time in stop_times:
            point = stop_time.get("stop_point", {})
            area = point.get("stop_area") or {}
            station_id = area.get("id") or point.get("id")
            name = area.get("name") or point.get("name")
            coord = area.get("coord") or point.get("coord") or {}
            if not station_id or not name:
                raise ValueError("Stop time has no station identity")
            try:
                lat, lon = float(coord["lat"]), float(coord["lon"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Missing coordinates for station {station_id}") from exc
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"Invalid coordinates for station {station_id}")
            self.stations.setdefault(station_id, {
                "name": name, "lat": lat, "lon": lon, "neighbors": [],
            })
            # Collapse consecutive platforms, but retain later visits in loops.
            if not path or path[-1] != station_id:
                path.append(station_id)
        if len(path) > 1:
            forward = tuple(path)
            self.paths.add(min(forward, forward[::-1]))

    def build(self) -> LineGraph:
        if not self.paths:
            raise ValueError("No usable station paths in Navitia response")
        maximal: list[tuple[str, ...]] = []
        for path in sorted(self.paths, key=lambda p: (-len(p), p)):
            if any(
                _is_subsequence(path, other) or _is_subsequence(path[::-1], other)
                for other in maximal
            ):
                continue
            maximal.append(path)

        neighbors: dict[str, set[str]] = {station_id: set() for station_id in self.stations}
        links: set[tuple[str, str]] = set()
        loop_links: set[tuple[str, str]] = set()
        for path in maximal:
            for first, second in zip(path, path[1:]):
                link = tuple(sorted((first, second)))
                links.add(link)
                if len(set(path)) != len(path):
                    loop_links.add(link)
        # Shared portions can be express even when the complete paths have
        # different termini. Only expand links witnessed inside a simple path;
        # graph-wide transitive reduction would incorrectly destroy loops.
        shortcuts: set[tuple[str, str]] = set()
        for path in maximal:
            if len(set(path)) != len(path):
                continue
            for index, first in enumerate(path):
                for second in path[index + 2:]:
                    link = tuple(sorted((first, second)))
                    if link in links and link not in loop_links:
                        shortcuts.add(link)
        for first, second in links - shortcuts:
            neighbors[first].add(second)
            neighbors[second].add(first)
        graph: LineGraph = {"stations": {
            station_id: {**station, "neighbors": sorted(neighbors[station_id])}
            for station_id, station in sorted(self.stations.items())
        }}
        validate_line_graph(graph)
        return graph


def _is_subsequence(path: tuple[str, ...], other: tuple[str, ...]) -> bool:
    iterator = iter(other)
    return all(any(candidate == station for candidate in iterator) for station in path)


def validate_line_graph(graph: LineGraph) -> None:
    if not isinstance(graph, dict):
        raise ValueError("Invalid station graph")
    stations = graph.get("stations")
    if not isinstance(stations, dict) or len(stations) < 2:
        raise ValueError("Station graph is empty or incomplete")
    for station_id, station in stations.items():
        if not isinstance(station, dict) or not isinstance(station.get("name"), str):
            raise ValueError(f"Invalid station {station_id}")
        lat, lon = station.get("lat"), station.get("lon")
        if (
            not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not math.isfinite(lat) or not math.isfinite(lon)
            or not (-90 <= lat <= 90 and -180 <= lon <= 180)
        ):
            raise ValueError(f"Invalid coordinates for station {station_id}")
        neighbors = station.get("neighbors")
        if (
            not isinstance(neighbors, list) or not neighbors
            or not all(isinstance(neighbor, str) for neighbor in neighbors)
            or len(neighbors) != len(set(neighbors))
        ):
            raise ValueError(f"Invalid neighbors for station {station_id}")
        for neighbor in neighbors:
            if neighbor == station_id or neighbor not in stations:
                raise ValueError(f"Invalid link {station_id} -> {neighbor}")
    for station_id, station in stations.items():
        for neighbor in station["neighbors"]:
            if station_id not in stations[neighbor]["neighbors"]:
                raise ValueError(f"Asymmetric link {station_id} -> {neighbor}")
