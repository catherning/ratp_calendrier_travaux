"use client";

import { DisruptionDetail } from "@/lib/types";
import { api } from "@/lib/api";
import { useState, useEffect } from "react";
import { causeLabel, effectLabel } from "@/lib/utils";

interface Props {
  disruption: DisruptionDetail;
  activePeriodIndex?: number; // Optional prop to pre-select a period from calendar clicks
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DisruptionCard({ disruption, activePeriodIndex }: Props) {
  const periods = disruption.periods ?? [];
  const hasMultiplePeriods = periods.length > 1;

  // Track the selected period index. -1 means "Toutes les dates (Export groupé)"
  const [selectedPeriodIndex, setSelectedPeriodIndex] = useState<number>(-1);

  // Sync state if activePeriodIndex is provided externally (e.g. from calendar click)
  useEffect(() => {
    if (activePeriodIndex !== undefined && activePeriodIndex !== null) {
      setSelectedPeriodIndex(activePeriodIndex);
    } else {
      setSelectedPeriodIndex(hasMultiplePeriods ? -1 : (periods[0]?.period_index ?? 0));
    }
  }, [activePeriodIndex, disruption, hasMultiplePeriods]);

  const [gcalLoading, setGcalLoading] = useState(false);

  const bg = `#${disruption.line_color}`;
  const fg = `#${disruption.line_text_color}`;

  const shortTitle = disruption.summary.split(" — ").slice(1).join(" — ") || disruption.summary;

  const handleGcal = async () => {
    const periodIdx = selectedPeriodIndex === -1 ? (periods[0]?.period_index ?? 0) : selectedPeriodIndex;
    setGcalLoading(true);
    try {
      const url = await api.getGoogleCalendarUrl(
        disruption.impact_id,
        disruption.line_code,
        periodIdx
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } finally {
      setGcalLoading(false);
    }
  };

  // Determine current display dates based on selected period
  const activePeriod = selectedPeriodIndex !== -1
    ? periods.find((p) => p.period_index === selectedPeriodIndex)
    : periods[0];

  const displayStart = activePeriod ? activePeriod.date_debut : disruption.date_debut;
  const displayEnd = selectedPeriodIndex !== -1 && activePeriod
    ? activePeriod.date_fin
    : (periods[periods.length - 1]?.date_fin ?? disruption.date_fin);

  const icsUrl = api.getIcsUrl(
    disruption.impact_id,
    disruption.line_code,
    selectedPeriodIndex === -1 ? null : selectedPeriodIndex
  );

  const isUpcoming = new Date(disruption.date_fin) >= new Date();

  return (
    <article
      id={`card-${disruption.id}`}
      className={`disruption-card${!isUpcoming ? " disruption-card--past" : ""}`}
    >
      {/* Line badge strip */}
      <div className="disruption-card__stripe" style={{ background: bg }} />

      <div className="disruption-card__body">
        {/* Header */}
        <header className="disruption-card__header">
          <span
            className="disruption-card__line-pill"
            style={{ background: bg, color: fg }}
          >
            {disruption.line_code}
          </span>

          <div className="disruption-card__meta">
            <span className="disruption-card__effect">
              {causeLabel(disruption.cause)} • {effectLabel(disruption.effect)}
            </span>
            {disruption.impacts_itinerary === false && (
              <span className="disruption-card__outside-badge">Hors trajet</span>
            )}
            {!isUpcoming && <span className="disruption-card__past-badge">Terminé</span>}
          </div>
        </header>

        {/* Title */}
        <h3 className="disruption-card__title">{shortTitle}</h3>

        {/* Multi-Period Selector Dropdown */}
        {hasMultiplePeriods && (
          <div className="disruption-card__period-selector" style={{ margin: "12px 0" }}>
            <label htmlFor={`period-select-${disruption.id}`} className="period-selector-label" style={{ fontSize: "0.8rem", color: "#8a99ad", marginRight: "8px" }}>
              🗓️ Choisir une date :
            </label>
            <select
              id={`period-select-${disruption.id}`}
              value={selectedPeriodIndex}
              onChange={(e) => setSelectedPeriodIndex(Number(e.target.value))}
              style={{
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                borderRadius: "6px",
                color: "#f8fafc",
                padding: "4px 8px",
                fontSize: "0.85rem",
                outline: "none",
                cursor: "pointer",
                maxWidth: "100%",
                transition: "border-color 0.2s"
              }}
              onFocus={(e) => e.target.style.borderColor = "rgba(255, 255, 255, 0.3)"}
              onBlur={(e) => e.target.style.borderColor = "rgba(255, 255, 255, 0.15)"}
            >
              <option value={-1} style={{ background: "#0f172a", color: "#f8fafc" }}>
                Toutes les dates ({periods.length} occurrences)
              </option>
              {periods.map((p, idx) => (
                <option key={idx} value={p.period_index} style={{ background: "#0f172a", color: "#f8fafc" }}>
                  Date {idx + 1}: du {formatDate(p.date_debut)} au {formatDate(p.date_fin)}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Dates */}
        <div className="disruption-card__dates" style={{ marginTop: hasMultiplePeriods ? "4px" : "12px" }}>
          <span>🗓️ {formatDate(displayStart)}</span>
          <span className="disruption-card__dates-sep">→</span>
          <span>{formatDate(displayEnd)}</span>
          {selectedPeriodIndex === -1 && hasMultiplePeriods && (
            <span style={{ fontSize: "0.75rem", background: "rgba(255,255,255,0.08)", padding: "2px 6px", borderRadius: "10px", marginLeft: "8px", verticalAlign: "middle" }}>
              Global
            </span>
          )}
        </div>

        {/* Stations */}
        {disruption.stations !== "toute la ligne" && (
          <p className="disruption-card__stations">
            🚉 {disruption.stations}
          </p>
        )}

        {/* Description */}
        <p className="disruption-card__text">{disruption.text}</p>

        {/* Actions */}
        <div className="disruption-card__actions">
          <a
            href={icsUrl}
            download
            className="btn btn--ics"
            id={`ics-${disruption.id}`}
            title={selectedPeriodIndex === -1 ? "Télécharger le calendrier complet (toutes les dates)" : "Télécharger pour cette date"}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/>
            </svg>
            {selectedPeriodIndex === -1 && hasMultiplePeriods ? "Outlook complet (ICS)" : "Outlook (ICS)"}
          </a>

          <a
            href={icsUrl}
            download
            className="btn btn--apple"
            id={`apple-${disruption.id}`}
            title={selectedPeriodIndex === -1 ? "Ajouter toutes les dates à Apple Calendar" : "Ajouter à Apple Calendar"}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.07 2.47.3 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.17c.66-.81 1.11-1.93.99-3.06-.96.05-2.13.65-2.82 1.47-.6.7-1.13 1.84-.99 2.94.1.08.2.12.31.12.9 0 2.01-.54 2.51-1.47z"/>
            </svg>
            {selectedPeriodIndex === -1 && hasMultiplePeriods ? "Apple complet (iCal)" : "Apple Calendar"}
          </a>

          {selectedPeriodIndex === -1 && hasMultiplePeriods ? (
            <button
              className="btn btn--gcal"
              id={`gcal-${disruption.id}`}
              disabled
              style={{ opacity: 0.5, cursor: "not-allowed" }}
              title="L'import Google Calendar se fait date par date. Choisissez une date spécifique ci-dessus pour l'ajouter."
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11zM7 11h5v5H7z"/>
              </svg>
              Google Calendar
            </button>
          ) : (
            <button
              className="btn btn--gcal"
              id={`gcal-${disruption.id}`}
              onClick={handleGcal}
              disabled={gcalLoading}
              title="Ajouter à Google Calendar"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11zM7 11h5v5H7z"/>
              </svg>
              {gcalLoading ? "…" : "Google Calendar"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
