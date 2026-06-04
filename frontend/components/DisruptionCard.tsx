"use client";

import { DisruptionDetail } from "@/lib/types";
import { api } from "@/lib/api";
import { useState } from "react";

interface Props {
  disruption: DisruptionDetail;
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

export default function DisruptionCard({ disruption }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [gcalLoading, setGcalLoading] = useState(false);

  const bg = `#${disruption.line_color}`;
  const fg = `#${disruption.line_text_color}`;

  const shortTitle = disruption.summary.split(" — ").slice(1).join(" — ") || disruption.summary;

  const handleGcal = async () => {
    setGcalLoading(true);
    try {
      const url = await api.getGoogleCalendarUrl(
        disruption.impact_id,
        disruption.line_code,
        disruption.period_index
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } finally {
      setGcalLoading(false);
    }
  };

  const icsUrl = api.getIcsUrl(disruption.impact_id, disruption.line_code, disruption.period_index);

  const isUpcoming = new Date(disruption.date_fin) >= new Date();

  return (
    <article
      id={`card-${disruption.id}`}
      className={`disruption-card${expanded ? " disruption-card--expanded" : ""}${!isUpcoming ? " disruption-card--past" : ""}`}
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
              {effectLabel(disruption.effect)}
            </span>
            {!isUpcoming && <span className="disruption-card__past-badge">Terminé</span>}
          </div>
        </header>

        {/* Title */}
        <h3 className="disruption-card__title">{shortTitle}</h3>

        {/* Dates */}
        <div className="disruption-card__dates">
          <span>🗓 {formatDate(disruption.date_debut)}</span>
          <span className="disruption-card__dates-sep">→</span>
          <span>{formatDate(disruption.date_fin)}</span>
        </div>

        {/* Stations */}
        {disruption.stations !== "toute la ligne" && (
          <p className="disruption-card__stations">
            🚉 {disruption.stations}
          </p>
        )}

        {/* Expandable description */}
        <button
          className="disruption-card__expand-btn"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          id={`expand-${disruption.id}`}
        >
          {expanded ? "Masquer le détail ▲" : "Voir le détail ▼"}
        </button>

        {expanded && (
          <p className="disruption-card__text">{disruption.text}</p>
        )}

        {/* Actions */}
        <div className="disruption-card__actions">
          <a
            href={icsUrl}
            download
            className="btn btn--ics"
            id={`ics-${disruption.id}`}
            title="Ajouter à Outlook / Apple Calendar"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/>
            </svg>
            ICS / Outlook
          </a>

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
        </div>
      </div>
    </article>
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
