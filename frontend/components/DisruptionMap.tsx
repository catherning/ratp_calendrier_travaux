"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { DisruptionDetail, StationInfo, LineInfo, LineStationsData } from "@/lib/types";

// Robust station name normalization for accent-insensitive and case-insensitive matching
export function normalizeStationName(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // Remove accents
    .replace(/[^a-z0-9]/g, ""); // Keep only alphanumeric
}

interface Props {
  disruptions: DisruptionDetail[];
  stations: Record<string, LineStationsData>;
  onDisruptionClick: (disruption: DisruptionDetail) => void;
  lines: LineInfo[];
}

export default function DisruptionMap({ disruptions, stations, onDisruptionClick, lines }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layersRef = useRef<{
    stations: L.LayerGroup;
    lines: L.LayerGroup;
  } | null>(null);

  const [showLines, setShowLines] = useState(true);

  // Helper to match disruptions impacting a specific station on a line
  const getStationDisruptions = (stationName: string, lineCode: string): DisruptionDetail[] => {
    const normName = normalizeStationName(stationName);
    return disruptions.filter((d) => {
      if (d.line_code !== lineCode) return false;
      if (d.stations.toLowerCase() === "toute la ligne") return true;
      return d.stations
        .split(" | ")
        .map((s) => normalizeStationName(s))
        .includes(normName);
    });
  };

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

  // Initialize Leaflet Map once
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

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

    mapRef.current = map;
    layersRef.current = {
      stations: stationsLayer,
      lines: linesLayer,
    };

    // Bridge Leaflet Popup HTML clicks into React
    map.on("popupopen", (e) => {
      const container = e.popup.getElement();
      if (container) {
        const btns = container.querySelectorAll(".popup-details-btn");
        btns.forEach((btn) => {
          btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            const d = disruptions.find((x) => x.id === id);
            if (d) {
              onDisruptionClick(d);
              map.closePopup();
            }
          });
        });
      }
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        layersRef.current = null;
      }
    };
  }, [disruptions, onDisruptionClick]);

  // Render/Update stations and connection lines whenever dependencies change
  useEffect(() => {
    if (!mapRef.current || !layersRef.current) return;

    const { stations: stationsLayer, lines: linesLayer } = layersRef.current;

    // Clear previous elements
    stationsLayer.clearLayers();
    linesLayer.clearLayers();

    // Map bounds helper to auto-fit selected lines nicely
    const coordinates: L.LatLngExpression[] = [];

    // Draw elements for each selected line in our stations state
    Object.entries(stations).forEach(([lineCode, lineData]) => {
      if (!lineData) return;
      const stationList = lineData.stations || [];
      const routeList = lineData.routes || [];
      if (stationList.length === 0) return;

      const lineInfo = lines.find((l) => l.code === lineCode);
      const color = lineInfo ? lineInfo.color : "3b82f6"; // default blue

      // 1. Draw connection paths (polylines) if toggle is enabled
      if (showLines) {
        if (routeList.length > 0) {
          routeList.forEach((singleRoute) => {
            if (singleRoute.length > 1) {
              const pathPoints = singleRoute.map((st) => [st.lat, st.lon] as L.LatLngExpression);
              const polyline = L.polyline(pathPoints, {
                color: `#${color}`,
                weight: 4,
                opacity: 0.65,
                lineJoin: "round",
                lineCap: "round",
              });
              linesLayer.addLayer(polyline);
            }
          });
        } else if (stationList.length > 1) {
          // Fallback to connecting flat stations list (e.g. if routes was empty)
          const pathPoints = stationList.map((st) => [st.lat, st.lon] as L.LatLngExpression);
          const polyline = L.polyline(pathPoints, {
            color: `#${color}`,
            weight: 4,
            opacity: 0.65,
            lineJoin: "round",
            lineCap: "round",
          });
          linesLayer.addLayer(polyline);
        }
      }

      // 2. Draw station nodes (circles or pulsing indicators)
      stationList.forEach((st) => {
        coordinates.push([st.lat, st.lon]);

        const stationDisruptions = getStationDisruptions(st.name, lineCode);
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
    if (coordinates.length > 0 && mapRef.current) {
      const bounds = L.latLngBounds(coordinates);
      mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [stations, disruptions, showLines, lines]);

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
