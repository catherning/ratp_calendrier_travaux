"use client";

import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import listPlugin from "@fullcalendar/list";
import frLocale from "@fullcalendar/core/locales/fr";
import { DisruptionDetail } from "@/lib/types";
import { EventClickArg } from "@fullcalendar/core";

interface Props {
  disruptions: DisruptionDetail[];
  onEventClick?: (disruption: DisruptionDetail, periodIndex: number) => void;
}

export default function DisruptionCalendar({ disruptions, onEventClick }: Props) {
  // Use flatMap to project each period of a grouped disruption as an individual event on the calendar
  const events = disruptions.flatMap((d) => {
    const periods = d.periods ?? [];
    if (periods.length > 0) {
      return periods.map((p) => ({
        id: `${d.impact_id}__p${p.period_index}`,
        title: `${d.line_code} — ${d.summary.split(" — ").slice(1).join(" — ")}`,
        start: p.date_debut,
        end: p.date_fin,
        backgroundColor: `#${d.line_color}`,
        borderColor: `#${d.line_color}`,
        textColor: `#${d.line_text_color}`,
        extendedProps: { disruption: d, activePeriodIndex: p.period_index },
      }));
    } else {
      // Fallback for any disruption without periods explicitly parsed
      return [{
        id: d.id,
        title: `${d.line_code} — ${d.summary.split(" — ").slice(1).join(" — ")}`,
        start: d.date_debut,
        end: d.date_fin,
        backgroundColor: `#${d.line_color}`,
        borderColor: `#${d.line_color}`,
        textColor: `#${d.line_text_color}`,
        extendedProps: { disruption: d, activePeriodIndex: 0 },
      }];
    }
  });

  const handleClick = (info: EventClickArg) => {
    const d = info.event.extendedProps.disruption as DisruptionDetail;
    const activePeriodIdx = info.event.extendedProps.activePeriodIndex as number;
    onEventClick?.(d, activePeriodIdx);
  };

  return (
    <div className="calendar-wrapper" id="disruption-calendar">
      <FullCalendar
        plugins={[dayGridPlugin, listPlugin]}
        initialView="dayGridMonth"
        locale={frLocale}
        events={events}
        eventClick={handleClick}
        headerToolbar={{
          left: "prev,next today",
          center: "title",
          right: "dayGridMonth,listMonth",
        }}
        height="auto"
        eventDisplay="block"
        dayMaxEvents={4}
        nowIndicator
        eventTimeFormat={{
          hour: "2-digit",
          minute: "2-digit",
          meridiem: false,
          hour12: false,
        }}
      />
    </div>
  );
}
