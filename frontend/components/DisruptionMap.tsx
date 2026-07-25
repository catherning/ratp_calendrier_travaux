"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { DisruptionDetail, StationInfo, LineInfo, LineStationsData, GraphStationInfo, JourneyItinerary } from "@/lib/types";

// Robust station name normalization for accent-insensitive and case-insensitive matching
export function normalizeStationName(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // Remove accents
    .replace(/[^a-z0-9]/g, ""); // Keep only alphanumeric
}

// Haversine formula to compute great-circle distance between two points in km
export function getDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Splits a list of route stop points into separate contiguous segments if distance exceeds maxDistance
export function splitRouteIntoSegments(
  routePoints: { lat: number; lon: number }[],
  maxDistance: number
): L.LatLngExpression[][] {
  const segments: L.LatLngExpression[][] = [];
  let currentSegment: L.LatLngExpression[] = [];

  routePoints.forEach((pt, idx) => {
    if (idx === 0) {
      currentSegment.push([pt.lat, pt.lon]);
      return;
    }

    const prev = routePoints[idx - 1];
    const dist = getDistance(prev.lat, prev.lon, pt.lat, pt.lon);

    if (dist > maxDistance) {
      if (currentSegment.length > 1) {
        segments.push(currentSegment);
      }
      currentSegment = [[pt.lat, pt.lon]];
    } else {
      currentSegment.push([pt.lat, pt.lon]);
    }
  });

  if (currentSegment.length > 1) {
    segments.push(currentSegment);
  }

  return segments;
}

// ── NLP & Geographic Segment Expansion Helpers ───────────────────────────────

/**
 * Finds all occurrences of station names in a text, sorting by length descending
 * to avoid matching substrings of longer station names (e.g. matching "Noisy-le-Grand"
 * inside "Noisy-le-Grand Mont d'Est").
 */
export function findStationsInText(text: string, stations: StationInfo[]): { station: StationInfo; index: number }[] {
  const normText = normalizeStationName(text);
  const matches: { station: StationInfo; index: number }[] = [];

  // Sort by name length descending to match longer names first
  const sortedStations = [...stations].sort((a, b) => b.name.length - a.name.length);

  // Keep track of matched character intervals to avoid overlapping matches
  const matchedIntervals: [number, number][] = [];

  sortedStations.forEach((st) => {
    const normName = normalizeStationName(st.name);
    if (normName.length < 3) return;

    let idx = normText.indexOf(normName);
    while (idx !== -1) {
      const start = idx;
      const end = idx + normName.length;

      // Check if this interval overlaps with any already matched interval
      const isOverlapping = matchedIntervals.some(
        ([s, e]) => (start >= s && start < e) || (end > s && end <= e) || (s >= start && s < end)
      );

      if (!isOverlapping) {
        matches.push({ station: st, index: idx });
        matchedIntervals.push([start, end]);
      }

      idx = normText.indexOf(normName, idx + 1);
    }
  });

  // Sort matches by their original occurrence order in the text
  return matches.sort((a, b) => a.index - b.index);
}

/**
 * Extract segment endpoints (from, to) from disruption summary & text using NLP heuristics.
 */
export function extractSegmentEndpoints(
  summary: string,
  text: string,
  stations: StationInfo[]
): [StationInfo, StationInfo] | null {
  const combinedText = `${summary} | ${text}`.toLowerCase();

  // Segment keywords
  const hasSegmentKeywords =
    combinedText.includes("entre") ||
    combinedText.includes("interrompu de") ||
    combinedText.includes("interruption entre") ||
    combinedText.includes("fermeture entre") ||
    combinedText.includes("ferme entre");

  if (!hasSegmentKeywords) return null;

  // Find all station matches in the text
  const matches = findStationsInText(combinedText, stations);

  if (matches.length >= 2) {
    const entreIdx = combinedText.indexOf("entre");
    const deIdx = combinedText.indexOf("interrompu de");
    const keywordIdx = entreIdx !== -1 ? entreIdx : (deIdx !== -1 ? deIdx : 0);

    // Prioritize stations mentioned after the segment keyword
    const matchesAfterKeyword = matches.filter((m) => m.index >= keywordIdx);
    if (matchesAfterKeyword.length >= 2) {
      return [matchesAfterKeyword[0].station, matchesAfterKeyword[1].station];
    }
    return [matches[0].station, matches[1].station];
  }

  return null;
}

/**
 * Resolve endpoints for a disruption, checking both split lists and text.
 */
export function resolveEndpoints(d: DisruptionDetail, stations: StationInfo[]): [StationInfo, StationInfo] | null {
  const dStations = d.stations.split(" | ").map((s) => s.trim());
  if (dStations.length === 2) {
    const stA = stations.find((st) => normalizeStationName(st.name) === normalizeStationName(dStations[0]));
    const stB = stations.find((st) => normalizeStationName(st.name) === normalizeStationName(dStations[1]));
    if (stA && stB) {
      return [stA, stB];
    }
  }

  return extractSegmentEndpoints(d.summary, d.text, stations);
}

/**
 * Traverses all geographic routes to find intermediate stations between two endpoints.
 */
export function getSegmentStations(stA: StationInfo, stB: StationInfo, lineData: LineStationsData): Set<string> {
  const result = new Set<string>();
  const stationsGraph = lineData.stations;

  if (!stationsGraph || !stationsGraph[stA.id] || !stationsGraph[stB.id]) {
    result.add(normalizeStationName(stA.name));
    result.add(normalizeStationName(stB.name));
    return result;
  }

  // Find shortest path between stA.id and stB.id using BFS
  const queue: string[] = [stA.id];
  const visited = new Set<string>([stA.id]);
  const parent: Record<string, string> = {};

  let found = false;
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === stB.id) {
      found = true;
      break;
    }

    const node = stationsGraph[current];
    if (node && node.neighbors) {
      for (const nbor of node.neighbors) {
        if (!visited.has(nbor)) {
          visited.add(nbor);
          parent[nbor] = current;
          queue.push(nbor);
        }
      }
    }
  }

  if (found) {
    let curr = stB.id;
    while (curr) {
      const node = stationsGraph[curr];
      if (node) {
        result.add(normalizeStationName(node.name));
      }
      curr = parent[curr];
    }
  } else {
    // Fallback
    result.add(normalizeStationName(stA.name));
    result.add(normalizeStationName(stB.name));
  }

  return result;
}

export function findShortestPathBetweenNames(
  fromName: string,
  toName: string,
  stationsGraph: Record<string, GraphStationInfo>
): string[] | null {
  const normFrom = normalizeStationName(fromName);
  const normTo = normalizeStationName(toName);

  let startId: string | null = null;
  let endId: string | null = null;

  for (const [id, st] of Object.entries(stationsGraph)) {
    const norm = normalizeStationName(st.name);
    if (norm === normFrom) startId = id;
    if (norm === normTo) endId = id;
    if (startId && endId) break;
  }

  if (!startId || !endId) return null;

  // BFS
  const queue: string[] = [startId];
  const visited = new Set<string>([startId]);
  const parent: Record<string, string> = {};

  let found = false;
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === endId) {
      found = true;
      break;
    }

    const node = stationsGraph[current];
    if (node && node.neighbors) {
      for (const nbor of node.neighbors) {
        if (!visited.has(nbor)) {
          visited.add(nbor);
          parent[nbor] = current;
          queue.push(nbor);
        }
      }
    }
  }

  if (!found) return null;

  const path: string[] = [];
  let curr = endId;
  while (curr) {
    path.push(curr);
    curr = parent[curr];
  }
  return path.reverse();
}

/**
 * Computes all impacted station names (normalized) for a given disruption.
 */
export function computeImpactedStations(d: DisruptionDetail, lineData: LineStationsData): Set<string> {
  const result = new Set<string>();
  if (!lineData || !lineData.stations) return result;

  const stationList = Object.entries(lineData.stations).map(([id, st]) => ({
    id,
    name: st.name,
    lat: st.lat,
    lon: st.lon,
  }));

  // Try to resolve segment endpoints
  const endpoints = resolveEndpoints(d, stationList);
  if (endpoints) {
    const [stA, stB] = endpoints;
    return getSegmentStations(stA, stB, lineData);
  }

  // Fallback to traditional matching
  if (d.stations.toLowerCase() === "toute la ligne") {
    stationList.forEach((st) => result.add(normalizeStationName(st.name)));
  } else {
    d.stations.split(" | ").forEach((s) => {
      result.add(normalizeStationName(s.trim()));
    });
  }

  return result;
}

// ── Main Component ───────────────────────────────────────────────────────────

interface Props {
  disruptions: DisruptionDetail[];
  stations: Record<string, LineStationsData>;
  onDisruptionClick: (disruption: DisruptionDetail) => void;
  lines: LineInfo[];
  activeItinerary?: JourneyItinerary | null;
}

export default function DisruptionMap({ disruptions, stations, onDisruptionClick, lines, activeItinerary }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [showLines, setShowLines] = useState(true);

  // Keep latest disruptions and click callbacks in stable refs to avoid tearing down map
  const disruptionsRef = useRef(disruptions);
  disruptionsRef.current = disruptions;

  const onDisruptionClickRef = useRef(onDisruptionClick);
  onDisruptionClickRef.current = onDisruptionClick;

  const layersRef = useRef<{
    stations: L.LayerGroup;
    lines: L.LayerGroup;
  } | null>(null);

  // Helper to create beautiful, customized, pulsing Leaflet DivIcons
  const createPulsingIcon = (color: string) => {
    return L.divIcon({
      className: "custom-pulsing-icon",
      html: `
        <div class="pulsing-marker-wrapper">
          <div class="pulsing-ring" style="border-color: #${color}; animation: ripple 1.6s infinite ease-out;"></div>
          <div class="pulsing-dot" style="background-color: #${color}; box-shadow: 0 0 10px #${color}aa;"></div>
        </div>
      `,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
  };

  // Initialize Leaflet Map once on mount
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Paris geographical center
    const center: L.LatLngExpression = [48.8566, 2.3522];
    const map = L.map(mapContainerRef.current, {
      center,
      zoom: 12,
      zoomControl: false,
    });

    // Elegant zoom control position
    L.control.zoom({ position: "bottomright" }).addTo(map);

    // Load CartoDB Dark Matter tiles (simplified vector-like transit styling)
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);

    // Setup Layer Groups
    const stationsLayer = L.layerGroup().addTo(map);
    const linesLayer = L.layerGroup().addTo(map);

    layersRef.current = {
      stations: stationsLayer,
      lines: linesLayer,
    };

    setMapInstance(map);

    // Bridge Leaflet Popup HTML clicks into React
    map.on("popupopen", (e) => {
      const container = e.popup.getElement();
      if (container) {
        const btns = container.querySelectorAll(".popup-details-btn");
        btns.forEach((btn) => {
          btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            const d = disruptionsRef.current.find((x) => x.id === id);
            if (d) {
              onDisruptionClickRef.current(d);
              map.closePopup();
            }
          });
        });
      }
    });

    return () => {
      map.remove();
      setMapInstance(null);
      layersRef.current = null;
    };
  }, []);

  // Render/Update stations and connection lines whenever dependencies change
  useEffect(() => {
    if (!mapInstance || !layersRef.current) return;

    const { stations: stationsLayer, lines: linesLayer } = layersRef.current;

    // Clear previous elements
    stationsLayer.clearLayers();
    linesLayer.clearLayers();

    // Map bounds helper to auto-fit selected lines nicely
    const coordinates: L.LatLngExpression[] = [];

    // Pre-compute a map of disruption ID -> Set of impacted station names (normalized)
    const disruptionImpacts: Record<string, Set<string>> = {};
    disruptions.forEach((d) => {
      const lineData = stations[d.line_code];
      if (lineData) {
        disruptionImpacts[d.id] = computeImpactedStations(d, lineData);
      } else {
        disruptionImpacts[d.id] = new Set();
      }
    });

    // Pre-calculate active itinerary station names and traversed sections if activeItinerary is present
    const itineraryStationNames = new Set<string>();
    const itinerarySectionsByLine: Record<string, { from: string; to: string }[]> = {};

    if (activeItinerary) {
      activeItinerary.sections.forEach((sec) => {
        if (sec.type === "public_transport" && sec.line_code) {
          if (!itinerarySectionsByLine[sec.line_code]) {
            itinerarySectionsByLine[sec.line_code] = [];
          }
          itinerarySectionsByLine[sec.line_code].push({
            from: sec.from_name,
            to: sec.to_name,
          });

          itineraryStationNames.add(normalizeStationName(sec.from_name));
          itineraryStationNames.add(normalizeStationName(sec.to_name));
        }
      });

      // Expand sections to get all intermediate stations on those line routes
      Object.entries(itinerarySectionsByLine).forEach(([lc, sectionsList]) => {
        const lineData = stations[lc];
        if (!lineData || !lineData.stations) return;
        const stationList: StationInfo[] = Object.entries(lineData.stations).map(([id, st]) => ({
          id,
          name: st.name,
          lat: st.lat,
          lon: st.lon,
        }));

        sectionsList.forEach(({ from, to }) => {
          const stA = stationList.find((st) => normalizeStationName(st.name) === normalizeStationName(from));
          const stB = stationList.find((st) => normalizeStationName(st.name) === normalizeStationName(to));
          if (stA && stB) {
            const segment = getSegmentStations(stA, stB, lineData);
            segment.forEach((norm) => itineraryStationNames.add(norm));
          }
        });
      });
    }

    // Draw elements for each selected line in our stations state
    Object.entries(stations).forEach(([lineCode, lineData]) => {
      if (!lineData || !lineData.stations) return;
      const stationList: StationInfo[] = Object.entries(lineData.stations).map(([id, st]) => ({
        id,
        name: st.name,
        lat: st.lat,
        lon: st.lon,
      }));
      if (stationList.length === 0) return;

      const lineInfo = lines.find((l) => l.code === lineCode);
      const color = lineInfo ? lineInfo.color : "3b82f6"; // default blue

      // 1. Draw connection paths (polylines) if toggle is enabled
      if (showLines) {
        if (activeItinerary) {
          // If we are in itinerary mode, only draw polylines for the sections traversed
          const sectionsList = itinerarySectionsByLine[lineCode] || [];
          sectionsList.forEach(({ from, to }) => {
            const pathIds = findShortestPathBetweenNames(from, to, lineData.stations);
            if (pathIds && pathIds.length > 1) {
              for (let i = 0; i < pathIds.length - 1; i++) {
                const nodeA = lineData.stations[pathIds[i]];
                const nodeB = lineData.stations[pathIds[i+1]];
                if (nodeA && nodeB) {
                  const polyline = L.polyline([[nodeA.lat, nodeA.lon], [nodeB.lat, nodeB.lon]], {
                    color: `#${color}`,
                    weight: 4,
                    opacity: 0.65,
                    lineJoin: "round",
                    lineCap: "round",
                  });
                  linesLayer.addLayer(polyline);
                }
              }
            }
          });
        } else {
          // Standard: Draw all unique physical links of the line's graph
          const drawnLinks = new Set<string>();
          Object.entries(lineData.stations).forEach(([stId, stNode]) => {
            stNode.neighbors.forEach((nborId) => {
              const nborNode = lineData.stations[nborId];
              if (nborNode) {
                const linkKey = stId < nborId ? `${stId}-${nborId}` : `${nborId}-${stId}`;
                if (!drawnLinks.has(linkKey)) {
                  drawnLinks.add(linkKey);
                  
                  const polyline = L.polyline([[stNode.lat, stNode.lon], [nborNode.lat, nborNode.lon]], {
                    color: `#${color}`,
                    weight: 4,
                    opacity: 0.65,
                    lineJoin: "round",
                    lineCap: "round",
                  });
                  linesLayer.addLayer(polyline);
                }
              }
            });
          });
        }
      }

      // 2. Draw station nodes (circles or pulsing indicators)
      stationList.forEach((st) => {
        if (typeof st.lat !== "number" || typeof st.lon !== "number" || isNaN(st.lat) || isNaN(st.lon)) return;
        const normName = normalizeStationName(st.name);

        // If in itinerary mode, skip stations that are not on the active itinerary path!
        if (activeItinerary && !itineraryStationNames.has(normName)) {
          return;
        }

        coordinates.push([st.lat, st.lon]);

        // Find disruptions of this line that impact this specific station
        const stationDisruptions = disruptions.filter((d) => {
          if (d.line_code !== lineCode) return false;
          const impacts = disruptionImpacts[d.id];
          return impacts ? impacts.has(normName) : false;
        });

        const isImpacted = stationDisruptions.length > 0;
        let marker: L.Layer;

        if (isImpacted) {
          // Dynamic pulsing marker for impacted stations
          marker = L.marker([st.lat, st.lon], {
            icon: createPulsingIcon(color),
          });

          // Build popup listing active construction works at this station
          const popupContent = `
            <div class="popup-wrapper">
              <div class="popup-header">
                <span class="popup-line-badge" style="background-color: #${color}; color: #${lineInfo?.text_color || "fff"};">
                  ${lineCode}
                </span>
                <span class="popup-station-name">${st.name}</span>
              </div>
              <div class="popup-body">
                <p class="popup-warning-title">⚠️ ${stationDisruptions.length} Travaux en cours :</p>
                <div class="popup-list">
                  ${stationDisruptions
                    .map((d) => {
                      const summaryClean = d.summary.split(" — ").slice(1).join(" — ");
                      return `
                      <div class="popup-item">
                        <div class="popup-item-summary">${summaryClean}</div>
                        <div class="popup-item-dates">du ${new Date(d.date_debut).toLocaleDateString("fr-FR")} au ${new Date(d.date_fin).toLocaleDateString("fr-FR")}</div>
                        <button class="popup-details-btn btn btn--primary btn--small" data-id="${d.id}">
                          Voir détails ➔
                        </button>
                      </div>
                    `;
                    })
                    .join("")}
                </div>
              </div>
            </div>
          `;
          marker.bindPopup(popupContent, { minWidth: 260 });
        } else {
          // Standard elegant circle marker for clean stations
          marker = L.circleMarker([st.lat, st.lon], {
            radius: 5,
            fillColor: `#${color}`,
            color: "#ffffff",
            weight: 1.5,
            fillOpacity: 0.9,
          });

          const popupContent = `
            <div class="popup-wrapper popup-wrapper--clean">
              <div class="popup-header">
                <span class="popup-line-badge" style="background-color: #${color}; color: #${lineInfo?.text_color || "fff"};">
                  ${lineCode}
                </span>
                <span class="popup-station-name">${st.name}</span>
              </div>
              <div class="popup-clean-body">
                <span class="popup-clean-badge">✅ Service normal</span>
                <p class="popup-clean-desc">Aucun travail majeur n'impacte cette station actuellement.</p>
              </div>
            </div>
          `;
          marker.bindPopup(popupContent, { minWidth: 200 });
        }

        // Add Hover Tooltip
        const tooltipContent = `
          <div class="map-tooltip">
            <strong>${st.name}</strong> <span class="map-tooltip-line" style="color: #${color};">Ligne ${lineCode}</span>
          </div>
        `;
        marker.bindTooltip(tooltipContent, {
          direction: "top",
          offset: [0, -4],
          opacity: 0.9,
        });

        stationsLayer.addLayer(marker);
      });
    });

    // Auto-fit selected stations nicely on screen
    if (coordinates.length > 0 && mapInstance) {
      const bounds = L.latLngBounds(coordinates);
      mapInstance.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [stations, disruptions, showLines, lines, mapInstance, activeItinerary]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Map Container */}
      <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />

      {/* Floating Map Controller */}
      <div
        style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          zIndex: 1000,
          background: "rgba(15, 23, 42, 0.8)",
          backdropFilter: "blur(16px)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          padding: "10px 14px",
          borderRadius: "12px",
          display: "flex",
          gap: "10px",
          alignItems: "center",
          boxShadow: "var(--shadow-md)",
          pointerEvents: "auto",
        }}
      >
        <input
          id="toggle-map-paths"
          type="checkbox"
          checked={showLines}
          onChange={(e) => setShowLines(e.target.checked)}
          style={{ cursor: "pointer", width: "16px", height: "16px", accentColor: "#2563eb" }}
        />
        <label
          htmlFor="toggle-map-paths"
          style={{
            fontSize: "0.8rem",
            fontWeight: "600",
            color: "#f8fafc",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          Afficher les tracés des lignes
        </label>
      </div>
    </div>
  );
}
