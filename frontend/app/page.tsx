"use client";

import { useEffect, useState, useTransition } from "react";
import { DisruptionDetail, PlaceResult, JourneyItinerary } from "@/lib/types";
import { api } from "@/lib/api";
import LineSelector from "@/components/LineSelector";
import DisruptionCard from "@/components/DisruptionCard";
import DisruptionCalendar from "@/components/DisruptionCalendar";

export default function Home() {
  const [selectedLines, setSelectedLines] = useState<string[]>(["1", "4", "A"]);
  const [disruptions, setDisruptions] = useState<DisruptionDetail[]>([]);
  const [viewMode, setViewMode] = useState<"list" | "calendar">("list");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Journey planning state
  const [fromPlace, setFromPlace] = useState<PlaceResult | null>(null);
  const [toPlace, setToPlace] = useState<PlaceResult | null>(null);
  const [isJourneyMode, setIsJourneyMode] = useState(false);
  const [journeyDisruptions, setJourneyDisruptions] = useState<DisruptionDetail[]>([]);
  const [activeItinerary, setActiveItinerary] = useState<JourneyItinerary | null>(null);

  // Filters state
  const [hidePastEvents, setHidePastEvents] = useState<boolean>(true);
  const [effectFilter, setEffectFilter] = useState<string>("ALL");

  // Modal event detail state
  const [activeDisruption, setActiveDisruption] = useState<DisruptionDetail | null>(null);

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
      setActiveItinerary(data.itinerary);
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
    setActiveItinerary(null);
  };

  const currentDisruptions = isJourneyMode ? journeyDisruptions : disruptions;

  // Apply filters to currentDisruptions
  const filteredDisruptions = currentDisruptions.filter((d) => {
    if (hidePastEvents) {
      const now = new Date();
      if (new Date(d.date_fin) < now) {
        return false;
      }
    }
    if (effectFilter !== "ALL" && d.effect !== effectFilter) {
      return false;
    }
    return true;
  });

  // Bulk Export ICS URL
  const bulkIcsUrl = filteredDisruptions.length > 0
    ? api.getBulkIcsUrl(
        filteredDisruptions.map((d) => d.id),
        filteredDisruptions.map((d) => d.line_code)
      )
    : "#";

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

          {/* Line Selector (Only relevant/active if not in journey mode) */}
          <div className={`card panel ${isJourneyMode ? "panel--disabled" : ""}`}>
            {isJourneyMode && (
              <div className="panel__overlay">
                <span>Itinéraire actif — Lignes automatiques</span>
              </div>
            )}
            <LineSelector selected={selectedLines} onChange={setSelectedLines} />
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

            <div className="filter-item">
              <label htmlFor="effect-filter-select" className="filter-label">
                Filtrer par impact :
              </label>
              <select
                id="effect-filter-select"
                className="filter-select"
                value={effectFilter}
                onChange={(e) => setEffectFilter(e.target.value)}
              >
                <option value="ALL">Tous les impacts</option>
                <option value="NO_SERVICE">Trafic interrompu</option>
                <option value="SIGNIFICANT_DELAYS">Retards importants</option>
                <option value="REDUCED_SERVICE">Service réduit</option>
                <option value="DETOUR">Déviation</option>
                <option value="MODIFIED_SERVICE">Service modifié</option>
              </select>
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

            {/* Proposed Itinerary Routing display */}
            {!loading && !error && activeItinerary && (
              <div className="card itinerary-card">
                <div className="itinerary-header">
                  <div className="itinerary-title">
                    <span>🗺️</span>
                    <h3>Itinéraire proposé</h3>
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

            {!loading && !error && filteredDisruptions.length === 0 && (
              <div className="state-message state-message--empty">
                <h3>🌿 Aucun travail détecté</h3>
                <p>
                  Toutes les lignes sélectionnées fonctionnent normalement ou n'ont pas de travaux signalés.
                </p>
              </div>
            )}

            {!loading && !error && filteredDisruptions.length > 0 && (
              <>
                {viewMode === "list" ? (
                  <div className="disruption-list">
                    {filteredDisruptions.map((d) => (
                      <DisruptionCard key={d.id} disruption={d} />
                    ))}
                  </div>
                ) : (
                  <div className="card calendar-card">
                    <DisruptionCalendar
                      disruptions={filteredDisruptions}
                      onEventClick={setActiveDisruption}
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
              
              <div className="modal__meta-grid">
                <div>
                  <strong>🗓 Début:</strong> {new Date(activeDisruption.date_debut).toLocaleString("fr-FR")}
                </div>
                <div>
                  <strong>🗓 Fin:</strong> {new Date(activeDisruption.date_fin).toLocaleString("fr-FR")}
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
                href={api.getIcsUrl(activeDisruption.impact_id, activeDisruption.line_code, activeDisruption.period_index)}
                download
                className="btn btn--ics"
              >
                Exporter (ICS)
              </a>
              <button
                className="btn btn--gcal"
                onClick={async () => {
                  const url = await api.getGoogleCalendarUrl(
                    activeDisruption.impact_id,
                    activeDisruption.line_code,
                    activeDisruption.period_index
                  );
                  window.open(url, "_blank", "noopener,noreferrer");
                }}
              >
                Google Calendar
              </button>
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
            // Slight timeout to let click item register before dropdown vanishes
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

function effectLabel(effect: string): string {
  const map: Record<string, string> = {
    NO_SERVICE: "Trafic interrompu",
    SIGNIFICANT_DELAYS: "Retards importants",
    REDUCED_SERVICE: "Service réduit",
    DETOUR: "Déviation",
    MODIFIED_SERVICE: "Service modifié",
  };
  return map[effect] ?? effect;
}

function causeLabel(cause: string): string {
  const map: Record<string, string> = {
    travaux: "Travaux",
    incident: "Incident",
    perturbation: "Perturbation",
    maintenance: "Maintenance",
    delays: "Délais",
    hors_travaux: "Hors travaux",
  };
  const key = cause ? cause.toLowerCase() : "";
  return map[key] ?? (cause ? cause.charAt(0).toUpperCase() + cause.slice(1) : "Travaux");
}
