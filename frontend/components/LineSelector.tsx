"use client";

import Image from "next/image";
import { LINE_COLORS, LINE_GROUPS, LINE_LOGOS, lineDisplayName } from "@/lib/lines";

interface Props {
  selected: string[];
  onChange: (codes: string[]) => void;
}

function LineBadge({
  code,
  active,
  onClick,
}: {
  code: string;
  active: boolean;
  onClick: () => void;
}) {
  const colors = LINE_COLORS[code] ?? { bg: "888888", text: "FFFFFF" };
  const logo = LINE_LOGOS[code];

  return (
    <button
      id={`line-badge-${code}`}
      onClick={onClick}
      title={`Ligne ${code}`}
      aria-pressed={active}
      className={`line-badge${active ? " line-badge--active" : ""}`}
      style={
        active
          ? { background: `#${colors.bg}`, color: `#${colors.text}`, borderColor: `#${colors.bg}` }
          : { borderColor: `#${colors.bg}55` }
      }
    >
      {logo ? (
        <Image
          src={logo}
          alt={`Ligne ${code}`}
          width={28}
          height={28}
          unoptimized
          className="line-badge__logo"
          style={{ filter: active ? "none" : "grayscale(80%) opacity(0.6)" }}
        />
      ) : (
        <span className="line-badge__label">{lineDisplayName(code)}</span>
      )}
    </button>
  );
}

function LineGroup({
  title,
  codes,
  selected,
  onToggle,
}: {
  title: string;
  codes: readonly string[];
  selected: string[];
  onToggle: (code: string) => void;
}) {
  const allSelected = codes.every((c) => selected.includes(c));

  const toggleAll = () => {
    if (allSelected) {
      codes.forEach(onToggle);
    } else {
      codes.filter((c) => !selected.includes(c)).forEach(onToggle);
    }
  };

  return (
    <div className="line-group">
      <div className="line-group__header">
        <span className="line-group__title">{title}</span>
        <button className="line-group__toggle-all" onClick={toggleAll} id={`toggle-all-${title}`}>
          {allSelected ? "Tout désélectionner" : "Tout sélectionner"}
        </button>
      </div>
      <div className="line-group__badges">
        {codes.map((code) => (
          <LineBadge
            key={code}
            code={code}
            active={selected.includes(code)}
            onClick={() => onToggle(code)}
          />
        ))}
      </div>
    </div>
  );
}

export default function LineSelector({ selected, onChange }: Props) {
  const toggle = (code: string) => {
    if (selected.includes(code)) {
      onChange(selected.filter((c) => c !== code));
    } else {
      onChange([...selected, code]);
    }
  };

  const clearAll = () => onChange([]);

  return (
    <section className="line-selector" aria-label="Sélection des lignes">
      <div className="line-selector__header">
        <h2 className="line-selector__title">Lignes suivies</h2>
        {selected.length > 0 && (
          <button id="clear-all-lines" className="line-selector__clear" onClick={clearAll}>
            Effacer tout ({selected.length})
          </button>
        )}
      </div>

      <LineGroup title="Métro" codes={LINE_GROUPS.metro} selected={selected} onToggle={toggle} />
      <LineGroup title="RER" codes={LINE_GROUPS.rer} selected={selected} onToggle={toggle} />
      <LineGroup title="Transilien" codes={LINE_GROUPS.transilien} selected={selected} onToggle={toggle} />
    </section>
  );
}
