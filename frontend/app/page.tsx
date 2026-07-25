"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { DisruptionDetail, PlaceResult, JourneyItinerary, LineInfo, StationInfo, LineStationsData } from "@/lib/types";
import { api } from "@/lib/api";
import { causeLabel, effectLabel } from "@/lib/utils";
import LineSelector from "@/components/LineSelector";
import DisruptionCard from "@/components/DisruptionCard";
import DisruptionCalendar from "@/components/DisruptionCalendar";
import dynamic from "next/dynamic";

const DisruptionMap = dynamic(() => import("@/components/DisruptionMap"), {
  ssr: false,
  loading: () => (
    <div className="state-message state-message--loading" style={{ height: "100%", minHeight: "400px" }}>
      <div className="loader"></div>
      <p>Chargement de la carte interactive...</p>
    </div>
  ),
});

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Home() {
  const [selectedLines, setSelectedLines] = useState<string[]>(["1", "4", "A"]);
  const [lines, setLines] = useState<LineInfo[]>([]);
  const [disruptions, setDisruptions] = useState<DisruptionDetail[]>([]);
  const [viewMode, setViewMode] = useState<"list" | "calendar" | "map">("list");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Journey planning state
  const [fromPlace, setFromPlace] = useState<PlaceResult | null>(null);
  const [toPlace, setToPlace] = useState<PlaceResult | null>(null);
  const [isJourneyMode, setIsJourneyMode] = useState(false);
  const [journeyDisruptions, setJourneyDisruptions] = useState<DisruptionDetail[]>([]);
  const [itineraries, setItineraries] = useState<JourneyItinerary[]>([]);
  const [activeItineraryIndex, setActiveItineraryIndex] = useState<number>(0);

  // Filters state
  const [hidePastEvents, setHidePastEvents] = useState<boolean>(true);
  const [selectedEffects, setSelectedEffects] = useState<string[]>([]);
  const [onlyDirectImpacts, setOnlyDirectImpacts] = useState<boolean>(true);

  // Stations state for map
  const [stations, setStations] = useState<Record<string, LineStationsData>>({});
  const [stationsLoading, setStationsLoading] = useState(false);

  // Date Filters state
  const [startDate, setStartDate] = useState<string>(() => {
    const today = new Date();
    return today.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState<string>("");

  // Modal event detail state
  const [activeDisruption, setActiveDisruption] = useState<DisruptionDetail | null>(null);
  const [modalPeriodIndex, setModalPeriodIndex] = useState<number>(-1);

  // Fetch available lines metadata once on mount
  useEffect(() => {
    api.getLines()
      .then(setLines)
      .catch((err) => console.error("Failed to load transit lines:", err));
  }, []);

  // Handle normal line disruption fetch
  useEffect(() => {
    if (isJourneyMode || selectedLines.length === 0) {
      if (selectedLines.length === 0) {
        setDisruptions([]);
      }
      return;
    }

    let active = true;
    const fetchDisruptions = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getDisruptions(selectedLines);
        if (active) setDisruptions(data);
      } catch (err) {
        if (active) setError("Impossible de charger les perturbations. Veuillez réessayer.");
        console.error(err);
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchDisruptions();
    return () => {
      active = false;
    };
  }, [selectedLines, isJourneyMode]);

  // Handle Journey search execution
  const handleJourneySearch = async () => {
    if (!fromPlace || !toPlace) return;
    setLoading(true);
    setError(null);
    setIsJourneyMode(true);
    try {
      const data = await api.getJourneyDisruptions(fromPlace.id, toPlace.id);
      setJourneyDisruptions(data.disruptions);
      const parsedItineraries = data.itineraries || (data.itinerary ? [data.itinerary] : []);
      setItineraries(parsedItineraries);
      setActiveItineraryIndex(0);
    } catch (err) {
      setError("Échec du calcul d'itinéraire ou de chargement des perturbations.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleClearJourney = () => {
    setIsJourneyMode(false);
    setFromPlace(null);
    setToPlace(null);
    setJourneyDisruptions([]);
    setItineraries([]);
    setActiveItineraryIndex(0);
  };

  const activeItinerary = itineraries[activeItineraryIndex] ?? null;
  const currentDisruptions = isJourneyMode ? journeyDisruptions : disruptions;

  // Determine active line codes to fetch station coordinates
  const activeLineCodes = useMemo(() => {
    return isJourneyMode
      ? activeItinerary
        ? Array.from(
            new Set(
              activeItinerary.sections
                .filter((s) => s.type === "public_transport" && s.line_code)
                .map((s) => s.line_code as string)
            )
          )
        : []
      : selectedLines;
  }, [isJourneyMode, activeItinerary, selectedLines]);

  // Reactively fetch station coordinates whenever activeLineCodes changes
  useEffect(() => {
    if (activeLineCodes.length === 0) {
      setStations({});
      return;
    }

    let active = true;
    setStationsLoading(true);
    api.getLineStations(activeLineCodes)
      .then((data) => {
        if (active) setStations(data);
      })
      .catch((err) => {
        console.error("Failed to load stations:", err);
      })
      .finally(() => {
        if (active) setStationsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activeLineCodes]);

  // Helper to check if a disruption impacts the currently active route itinerary
  const getDisruptionImpactsActiveRoute = (d: DisruptionDetail) => {
    if (!isJourneyMode || !activeItinerary) return true;
    const impactedIds = activeItinerary.impacted_disruption_ids ?? [];
    return (
      impactedIds.includes(d.id) ||
      impactedIds.includes(d.impact_id) ||
      impactedIds.some((id) => id.startsWith(d.impact_id))
    );
  };

  // Helper to get total count of disruptions impacting a specific itinerary option
  const getDisruptionCountForItinerary = (it: JourneyItinerary): number => {
    const impactedIds = it.impacted_disruption_ids ?? [];
    return journeyDisruptions.filter((d) => {
      return (
        impactedIds.includes(d.id) ||
        impactedIds.includes(d.impact_id) ||
        impactedIds.some((id) => id.startsWith(d.impact_id))
      );
    }).length;
  };

  // Apply filters to currentDisruptions
  const filteredDisruptions = currentDisruptions.filter((d) => {
    if (hidePastEvents) {
      const now = new Date();
      if (new Date(d.date_fin) < now) {
        return false;
      }
    }
    // Date Range Filters (Overlaps check)
    if (startDate) {
      const filterStart = new Date(startDate + "T00:00:00");
      if (new Date(d.date_fin) < filterStart) {
        return false;
      }
    }
    if (endDate) {
      const filterEnd = new Date(endDate + "T23:59:59");
      if (new Date(d.date_debut) > filterEnd) {
        return false;
      }
    }
    if (selectedEffects.length > 0 && !selectedEffects.includes(d.effect)) {
      return false;
    }
    if (isJourneyMode && onlyDirectImpacts && !getDisruptionImpactsActiveRoute(d)) {
      return false;
    }
    return true;
  });

  // Map disruption models with dynamic path impacts before rendering cards
  const disruptionsToRender = filteredDisruptions.map((d) => ({
    ...d,
    impacts_itinerary: isJourneyMode ? getDisruptionImpactsActiveRoute(d) : undefined,
  }));

  // Bulk Export ICS URL
  const bulkIcsUrl = filteredDisruptions.length > 0
    ? api.getBulkIcsUrl(
        filteredDisruptions.map((d) => d.id),
        filteredDisruptions.map((d) => d.line_code)
      )
    : "#";

  // Handle opening the details modal from calendar click with specific period
  const handleCalendarEventClick = (d: DisruptionDetail, periodIndex: number) => {
    setActiveDisruption(d);
    setModalPeriodIndex(periodIndex);
  };

  const handleCardClick = (d: DisruptionDetail) => {
    setActiveDisruption(d);
    setModalPeriodIndex(d.periods && d.periods.length > 1 ? -1 : (d.periods?.[0]?.period_index ?? 0));
  };

  return (
    <div className="app-container">
      {/* Premium Header */}
      <header className="app-header">
        <div className="app-header__logo-container">
          <div className="app-header__logo">🚇</div>
          <div>
            <h1 className="app-header__title">Île-de-France Mobilités</h1>
            <p className="app-header__subtitle">Tableau de bord des Travaux & Interruptions de Service</p>
          </div>
        </div>
        <div className="app-header__badge">
          <span className="pulse-indicator"></span> Temps Réel
        </div>
      </header>

      {/* Main Responsive Grid */}
      <div className="app-grid">
        {/* Sidebar Controls */}
        <aside className="app-sidebar">
          {/* Journey Planner Panel */}
          <div className="card panel" style={{ overflow: "visible" }}>
            <h2 className="panel__title">📍 Recherche d'itinéraire</h2>
            <p className="panel__desc">Trouvez les perturbations spécifiques à votre trajet quotidien.</p>

            <div className="journey-form">
              <PlaceAutocomplete
                label="Station de départ"
                placeholder="Ex: Nation, Gare de Lyon..."
                value={fromPlace}
                onChange={setFromPlace}
              />
              <div className="journey-connector">↓</div>
              <PlaceAutocomplete
                label="Station d'arrivée"
                placeholder="Ex: La Défense, Vincennes..."
                value={toPlace}
                onChange={setToPlace}
              />

              <div className="journey-actions">
                <button
                  id="search-journey-btn"
                  className="btn btn--primary btn--full"
                  onClick={handleJourneySearch}
                  disabled={!fromPlace || !toPlace || loading}
                >
                  {loading && isJourneyMode ? "Calcul en cours..." : "Rechercher sur mon trajet"}
                </button>

                {isJourneyMode && (
                  <button
                    id="clear-journey-btn"
                    className="btn btn--secondary btn--full"
                    onClick={handleClearJourney}
                  >
                    Effacer l'itinéraire
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Date Range Filter Panel */}
          <div className="card panel">
            <h2 className="panel__title">📅 Période des travaux</h2>
            <p className="panel__desc">Filtrer les travaux planifiés sur une période spécifique.</p>
            <div className="date-filter-form" style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: "600", color: "#94a3b8" }}>Date de début</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid rgba(255, 255, 255, 0.15)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    padding: "8px 12px",
                    fontSize: "0.9rem",
                    outline: "none"
                  }}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: "600", color: "#94a3b8" }}>Date de fin</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid rgba(255, 255, 255, 0.15)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    padding: "8px 12px",
                    fontSize: "0.9rem",
                    outline: "none"
                  }}
                />
              </div>
              {(startDate || endDate) && (
                <button
                  className="btn btn--secondary"
                  onClick={() => {
                    setStartDate("");
                    setEndDate("");
                  }}
                  style={{ marginTop: "4px", padding: "6px 12px", fontSize: "0.8rem", width: "100%" }}
                >
                  Réinitialiser les dates
                </button>
              )}
            </div>
          </div>

          {/* Line Selector */}
          <div className={`card panel ${isJourneyMode ? "panel--disabled" : ""}`}>
            {isJourneyMode && (
              <div className="panel__overlay">
                <span>Itinéraire actif — Lignes automatiques</span>
              </div>
            )}
            <LineSelector lines={lines} selected={selectedLines} onChange={setSelectedLines} />
          </div>
        </aside>

        {/* Content Area */}
        <main className="app-main-content">
          {/* Toolbar / Actions */}
          <div className="toolbar">
            <div className="view-selector">
              <button
                id="view-list-tab"
                className={`view-selector__btn ${viewMode === "list" ? "view-selector__btn--active" : ""}`}
                onClick={() => setViewMode("list")}
              >
                📊 Liste ({filteredDisruptions.length})
              </button>
              <button
                id="view-calendar-tab"
                className={`view-selector__btn ${viewMode === "calendar" ? "view-selector__btn--active" : ""}`}
                onClick={() => setViewMode("calendar")}
              >
                📅 Calendrier
              </button>
              <button
                id="view-map-tab"
                className={`view-selector__btn ${viewMode === "map" ? "view-selector__btn--active" : ""}`}
                onClick={() => setViewMode("map")}
              >
                🗺️ Carte
              </button>
            </div>

            {filteredDisruptions.length > 0 && (
              <a
                href={bulkIcsUrl}
                download="travaux_idf_mobilites.ics"
                className="btn btn--bulk-ics"
                id="bulk-ics-download"
                title="Exporter tous ces événements dans mon calendrier"
              >
                📥 Exporter tout en ICS
              </a>
            )}
          </div>

          {/* Filter Bar */}
          <div className="filter-bar">
            <div className="filter-item">
              <input
                id="hide-past-events-checkbox"
                type="checkbox"
                className="filter-checkbox"
                checked={hidePastEvents}
                onChange={(e) => setHidePastEvents(e.target.checked)}
              />
              <label htmlFor="hide-past-events-checkbox" className="filter-label">
                Masquer les travaux terminés
              </label>
            </div>

            {isJourneyMode && (
              <div className="filter-item">
                <input
                  id="only-direct-impacts-checkbox"
                  type="checkbox"
                  className="filter-checkbox"
                  checked={onlyDirectImpacts}
                  onChange={(e) => setOnlyDirectImpacts(e.target.checked)}
                />
                <label htmlFor="only-direct-impacts-checkbox" className="filter-label" title="Afficher uniquement les perturbations touchant les stations de mon trajet calculé">
                  Uniquement sur mon trajet
                </label>
              </div>
            )}

            <div className="filter-item filter-item--multi">
              <label className="filter-label">
                Filtrer par impact :
              </label>
              <div className="effect-toggle-group">
                <button
                  type="button"
                  className={`effect-toggle-btn ${selectedEffects.length === 0 ? "effect-toggle-btn--active" : ""}`}
                  onClick={() => setSelectedEffects([])}
                >
                  Tous
                </button>
                {[
                  { value: "NO_SERVICE", label: "🚫 Interrompu" },
                  { value: "SIGNIFICANT_DELAYS", label: "⚠️ Retards" },
                  { value: "REDUCED_SERVICE", label: "📉 Service réduit" },
                  { value: "DETOUR", label: "↪️ Déviation" },
                  { value: "MODIFIED_SERVICE", label: "🔧 Modifié" },
                ].map((eff) => {
                  const isSelected = selectedEffects.includes(eff.value);
                  return (
                    <button
                      key={eff.value}
                      type="button"
                      className={`effect-toggle-btn ${isSelected ? "effect-toggle-btn--active" : ""}`}
                      onClick={() => {
                        if (isSelected) {
                          setSelectedEffects(selectedEffects.filter((x) => x !== eff.value));
                        } else {
                          setSelectedEffects([...selectedEffects, eff.value]);
                        }
                      }}
                    >
                      {eff.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Main Content Render */}
          <div className="content-container">
            {loading && (
              <div className="state-message state-message--loading">
                <div className="loader"></div>
                <p>Chargement des perturbations IDFM...</p>
              </div>
            )}

            {error && !loading && (
              <div className="state-message state-message--error">
                <p>❌ {error}</p>
              </div>
            )}

            {/* Alternative itineraries tab selector */}
            {!loading && !error && itineraries.length > 0 && (
              <div className="itineraries-selector" style={{ marginBottom: "20px" }}>
                <h3 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#8a99ad", marginBottom: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>🗺️</span> Trajets proposés ({itineraries.length} options disponibles) :
                </h3>
                <div style={{ display: "flex", gap: "12px", overflowX: "auto", paddingBottom: "10px" }}>
                  {itineraries.map((it, idx) => {
                    const durationMin = Math.round(it.duration / 60);
                    const depTime = new Date(it.departure_time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
                    const arrTime = new Date(it.arrival_time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
                    const isSelected = idx === activeItineraryIndex;

                    const linesUsed = it.sections
                      .filter(s => s.type === "public_transport" && s.line_code)
                      .map(s => s.line_code);

                    const disruptionCount = getDisruptionCountForItinerary(it);

                    return (
                      <button
                        key={idx}
                        onClick={() => setActiveItineraryIndex(idx)}
                        style={{
                          background: isSelected ? "rgba(255, 255, 255, 0.12)" : "rgba(255, 255, 255, 0.04)",
                          border: isSelected ? "1px solid rgba(255, 255, 255, 0.35)" : "1px solid rgba(255, 255, 255, 0.1)",
                          borderRadius: "8px",
                          padding: "12px 18px",
                          color: "#f8fafc",
                          cursor: "pointer",
                          textAlign: "left",
                          minWidth: "180px",
                          transition: "all 0.25s ease",
                          boxShadow: isSelected ? "0 4px 16px rgba(0, 0, 0, 0.25)" : "none",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                          <span style={{ fontWeight: "700", fontSize: "1.1rem" }}>{durationMin} min</span>
                          <span style={{ fontSize: "0.7rem", fontWeight: "600", color: isSelected ? "#38bdf8" : "#8a99ad", textTransform: "uppercase" }}>
                            Option {idx + 1}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "8px" }}>
                          {depTime} - {arrTime}
                        </div>
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "8px" }}>
                          {linesUsed.map((lc, lIdx) => (
                            <span
                              key={lIdx}
                              style={{
                                fontSize: "0.7rem",
                                fontWeight: "700",
                                padding: "2px 6px",
                                borderRadius: "4px",
                                background: "rgba(255, 255, 255, 0.15)",
                                color: "#f8fafc"
                              }}
                            >
                              {lc}
                            </span>
                          ))}
                          {linesUsed.length === 0 && <span style={{ fontSize: "0.7rem", color: "#8a99ad" }}>🚶 Marche</span>}
                        </div>
                        <div style={{ marginTop: "6px" }}>
                          {disruptionCount > 0 ? (
                            <span style={{
                              fontSize: "0.7rem",
                              fontWeight: "700",
                              color: "#f87171",
                              background: "rgba(239, 68, 68, 0.15)",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "3px"
                            }}>
                              ⚠️ {disruptionCount} {disruptionCount > 1 ? "travaux" : "travail"}
                            </span>
                          ) : (
                            <span style={{
                              fontSize: "0.7rem",
                              fontWeight: "700",
                              color: "#34d399",
                              background: "rgba(16, 185, 129, 0.15)",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "3px"
                            }}>
                              ✅ Aucun impact
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Proposed Itinerary Timeline routing */}
            {!loading && !error && activeItinerary && (
              <div className="card itinerary-card" style={{ marginTop: "8px", marginBottom: "24px" }}>
                <div className="itinerary-header">
                  <div className="itinerary-title">
                    <span>🗺️</span>
                    <h3>Détails du trajet</h3>
                  </div>
                  <div className="itinerary-time">
                    <span className="itinerary-duration">{Math.round(activeItinerary.duration / 60)} min</span>
                    <span className="itinerary-period">
                      {new Date(activeItinerary.departure_time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                      {" - "}
                      {new Date(activeItinerary.arrival_time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>

                <div className="itinerary-timeline">
                  {activeItinerary.sections.map((section, idx) => {
                    const isTransit = section.type === "public_transport";
                    const isWalking = section.mode === "walking" || section.type === "street_network";

                    return (
                      <div key={idx} className="itinerary-segment">
                        {idx > 0 && <div className="itinerary-arrow">➔</div>}

                        <div className="itinerary-segment-content">
                          {isTransit ? (
                            <div className="itinerary-transit">
                              <span
                                className="itinerary-badge"
                                style={{
                                  backgroundColor: `#${section.line_color || "333"}`,
                                  color: `#${section.line_text_color || "fff"}`
                                }}
                              >
                                {section.line_code}
                              </span>
                              <div className="itinerary-segment-details">
                                <span className="itinerary-station-name">{section.from_name}</span>
                                <span className="itinerary-segment-duration">({Math.round(section.duration / 60)} min)</span>
                              </div>
                            </div>
                          ) : isWalking ? (
                            <div className="itinerary-walking" title={`Marcher de ${section.from_name} à ${section.to_name}`}>
                              <span className="itinerary-walking-icon">🚶</span>
                              <div className="itinerary-segment-details">
                                <span className="itinerary-station-name">{section.from_name === "Départ" ? "Marche" : section.from_name}</span>
                                <span className="itinerary-segment-duration">({Math.round(section.duration / 60)} min)</span>
                              </div>
                            </div>
                          ) : (
                            <div className="itinerary-other">
                              <span className="itinerary-other-icon">⏳</span>
                              <span className="itinerary-segment-duration">{Math.round(section.duration / 60)} min</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {!loading && !error && (
              <>
                {viewMode === "map" ? (
                  <div className="card map-card" style={{ height: "650px", minHeight: "650px", position: "relative" }}>
                    <DisruptionMap
                      disruptions={filteredDisruptions}
                      stations={stations}
                      onDisruptionClick={handleCardClick}
                      lines={lines}
                      activeItinerary={isJourneyMode ? activeItinerary : null}
                    />
                  </div>
                ) : filteredDisruptions.length === 0 ? (
                  <div className="state-message state-message--empty">
                    <h3>🌿 Pas de travaux détectés sur le trajet</h3>
                    <p>
                      Toutes les lignes sélectionnées fonctionnent normalement ou n'ont pas de travaux signalés.
                    </p>
                  </div>
                ) : viewMode === "list" ? (
                  <div className="disruption-list">
                    {disruptionsToRender.map((d) => (
                      <div key={d.id} onClick={() => handleCardClick(d)} style={{ cursor: "pointer" }}>
                        <DisruptionCard disruption={d} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="card calendar-card">
                    <DisruptionCalendar
                      disruptions={filteredDisruptions}
                      onEventClick={handleCalendarEventClick}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </main>
      </div>

      {/* Premium Event Detail Modal */}
      {activeDisruption && (
        <div className="modal-backdrop" onClick={() => setActiveDisruption(null)}>
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <header className="modal__header">
              <span
                className="modal__line-pill"
                style={{
                  background: `#${activeDisruption.line_color}`,
                  color: `#${activeDisruption.line_text_color}`,
                }}
              >
                {activeDisruption.line_code}
              </span>
              <h3 className="modal__title">{activeDisruption.line_name}</h3>
              <button className="modal__close" onClick={() => setActiveDisruption(null)}>
                ✕
              </button>
            </header>

            <div className="modal__body">
              <h4 className="modal__summary">{activeDisruption.summary.split(" — ").slice(1).join(" — ")}</h4>

              {/* Modal Period Selector */}
              {activeDisruption.periods && activeDisruption.periods.length > 1 && (
                <div style={{ marginBottom: "16px", background: "rgba(255,255,255,0.03)", padding: "10px 14px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <label htmlFor="modal-period-select" style={{ fontSize: "0.85rem", color: "#94a3b8", marginRight: "10px" }}>
                    🗓️ Choisir une date pour l'export :
                  </label>
                  <select
                    id="modal-period-select"
                    value={modalPeriodIndex}
                    onChange={(e) => setModalPeriodIndex(Number(e.target.value))}
                    style={{
                      background: "rgba(15, 23, 42, 0.6)",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      padding: "5px 10px",
                      fontSize: "0.85rem",
                      cursor: "pointer",
                      outline: "none"
                    }}
                  >
                    <option value={-1}>Toutes les dates ({activeDisruption.periods.length} occurrences)</option>
                    {activeDisruption.periods.map((p, idx) => (
                      <option key={idx} value={p.period_index}>
                        Date {idx + 1}: du {formatDate(p.date_debut)} au {formatDate(p.date_fin)}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="modal__meta-grid">
                <div>
                  <strong>🗓 Début:</strong> {formatDate(modalPeriodIndex === -1 ? activeDisruption.date_debut : (activeDisruption.periods.find(p => p.period_index === modalPeriodIndex)?.date_debut ?? activeDisruption.date_debut))}
                </div>
                <div>
                  <strong>🗓 Fin:</strong> {formatDate(modalPeriodIndex === -1 ? activeDisruption.date_fin : (activeDisruption.periods.find(p => p.period_index === modalPeriodIndex)?.date_fin ?? activeDisruption.date_fin))}
                </div>
                {activeDisruption.stations !== "toute la ligne" && (
                  <div className="modal__meta-full">
                    <strong>🚉 Stations impactées:</strong> {activeDisruption.stations}
                  </div>
                )}
                <div className="modal__meta-full">
                  <strong>⚠️ Impact:</strong> {causeLabel(activeDisruption.cause)} • {effectLabel(activeDisruption.effect)}
                </div>
              </div>

              <div className="modal__description">
                <h5>Détails des travaux & alternatives</h5>
                <p>{activeDisruption.text}</p>
              </div>
            </div>

            <footer className="modal__footer">
              <a
                href={api.getIcsUrl(activeDisruption.impact_id, activeDisruption.line_code, modalPeriodIndex === -1 ? null : modalPeriodIndex)}
                download
                className="btn btn--ics"
                title={modalPeriodIndex === -1 ? "Télécharger toutes les occurrences" : "Télécharger pour la date sélectionnée"}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style={{ marginRight: "4px" }}>
                  <path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/>
                </svg>
                {modalPeriodIndex === -1 && activeDisruption.periods && activeDisruption.periods.length > 1 ? "Outlook groupé (ICS)" : "Outlook (ICS)"}
              </a>

              <a
                href={api.getIcsUrl(activeDisruption.impact_id, activeDisruption.line_code, modalPeriodIndex === -1 ? null : modalPeriodIndex)}
                download
                className="btn btn--apple"
                title={modalPeriodIndex === -1 ? "Ajouter toutes les occurrences à Apple Calendar" : "Ajouter à Apple Calendar"}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style={{ marginRight: "4px" }}>
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.07 2.47.3 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.17c.66-.81 1.11-1.93.99-3.06-.96.05-2.13.65-2.82 1.47-.6.7-1.13 1.84-.99 2.94.1.08.2.12.31.12.9 0 2.01-.54 2.51-1.47z"/>
                </svg>
                {modalPeriodIndex === -1 && activeDisruption.periods && activeDisruption.periods.length > 1 ? "Apple groupé (iCal)" : "Apple Calendar"}
              </a>

              {modalPeriodIndex === -1 && activeDisruption.periods && activeDisruption.periods.length > 1 ? (
                <button
                  className="btn btn--gcal"
                  style={{ opacity: 0.5, cursor: "not-allowed" }}
                  disabled
                  title="L'import Google Calendar s'effectue date par date. Veuillez choisir une date spécifique."
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style={{ marginRight: "4px" }}>
                    <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11zM7 11h5v5H7z"/>
                  </svg>
                  Google Calendar
                </button>
              ) : (
                <button
                  className="btn btn--gcal"
                  title="Ajouter à Google Calendar"
                  onClick={async () => {
                    const url = await api.getGoogleCalendarUrl(
                      activeDisruption.impact_id,
                      activeDisruption.line_code,
                      modalPeriodIndex === -1 ? 0 : modalPeriodIndex
                    );
                    window.open(url, "_blank", "noopener,noreferrer");
                  }}
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style={{ marginRight: "4px" }}>
                    <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11zM7 11h5v5H7z"/>
                  </svg>
                  Google Calendar
                </button>
              )}
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Inner Components ─────────────────────────────────────────────────────────

function PlaceAutocomplete({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: PlaceResult | null;
  onChange: (place: PlaceResult | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (value) {
      setQuery(value.label);
    } else {
      setQuery("");
    }
  }, [value]);

  useEffect(() => {
    if (query.length < 2 || (value && query === value.label)) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const places = await api.getPlaces(query);
        setResults(places);
        setIsOpen(true);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, value]);

  return (
    <div className="autocomplete">
      <label className="autocomplete__label">{label}</label>
      <div className="autocomplete__wrapper">
        <input
          type="text"
          className="autocomplete__input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (value && e.target.value !== value.label) {
              onChange(null);
            }
          }}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          onBlur={() => {
            setTimeout(() => setIsOpen(false), 200);
          }}
        />
        {loading && <span className="autocomplete__loader"></span>}
        {isOpen && results.length > 0 && (
          <ul className="autocomplete__dropdown">
            {results.map((r) => (
              <li
                key={r.id}
                className="autocomplete__item"
                onMouseDown={() => {
                  onChange(r);
                  setQuery(r.label);
                  setIsOpen(false);
                }}
              >
                <div className="autocomplete__item-name">{r.name}</div>
                <div className="autocomplete__item-label">{r.label}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
