"use client";

import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import listPlugin from "@fullcalendar/list";
import frLocale from "@fullcalendar/core/locales/fr";
import { DisruptionDetail } from "@/lib/types";
import { EventClickArg } from "@fullcalendar/core";

interface Props {
  disruptions: DisruptionDetail[];
  onEventClick?: (disruption: DisruptionDetail) => void;
}

export default function DisruptionCalendar({ disruptions, onEventClick }: Props) {
  const events = disruptions.map((d) => ({
    id: d.id,
    title: `${d.line_code} — ${d.summary.split(" — ").slice(1).join(" — ")}`,
    start: d.date_debut,
    end: d.date_fin,
    backgroundColor: `#${d.line_color}`,
    borderColor: `#${d.line_color}`,
    textColor: `#${d.line_text_color}`,
    extendedProps: { disruption: d },
  }));

  const handleClick = (info: EventClickArg) => {
    const d = info.event.extendedProps.disruption as DisruptionDetail;
    onEventClick?.(d);
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
