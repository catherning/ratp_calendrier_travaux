"use client";

import Image from "next/image";
import { LineInfo } from "@/lib/types";

interface Props {
  lines: LineInfo[];
  selected: string[];
  onChange: (codes: string[]) => void;
}

function LineBadge({
  line,
  active,
  onClick,
}: {
  line: LineInfo;
  active: boolean;
  onClick: () => void;
}) {
  const bg = line.color;
  const fg = line.text_color;
  const logo = line.logo_url;

  return (
    <button
      id={`line-badge-${line.code}`}
      onClick={onClick}
      title={`Ligne ${line.code}`}
      aria-pressed={active}
      className={`line-badge${active ? " line-badge--active" : ""}`}
      style={
        active
          ? { background: `#${bg}`, color: `#${fg}`, borderColor: `#${bg}` }
          : { borderColor: `#${bg}55` }
      }
    >
      {logo ? (
        <Image
          src={logo}
          alt={`Ligne ${line.code}`}
          width={28}
          height={28}
          unoptimized
          className="line-badge__logo"
          style={{ filter: active ? "none" : "grayscale(80%) opacity(0.6)" }}
        />
      ) : (
        <span className="line-badge__label">{line.name}</span>
      )}
    </button>
  );
}

function LineGroup({
  title,
  lines,
  selected,
  onChange,
  onToggle,
}: {
  title: string;
  lines: LineInfo[];
  selected: string[];
  onChange: (codes: string[]) => void;
  onToggle: (code: string) => void;
}) {
  const allSelected = lines.length > 0 && lines.every((l) => selected.includes(l.code));

  const toggleAll = () => {
    const groupCodes = lines.map((l) => l.code);
    if (allSelected) {
      // De-select all lines in this group
      onChange(selected.filter((code) => !groupCodes.includes(code)));
    } else {
      // Select all lines in this group
      const newSelection = [...selected];
      groupCodes.forEach((code) => {
        if (!newSelection.includes(code)) {
          newSelection.push(code);
        }
      });
      onChange(newSelection);
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
        {lines.map((line) => (
          <LineBadge
            key={line.code}
            line={line}
            active={selected.includes(line.code)}
            onClick={() => onToggle(line.code)}
          />
        ))}
      </div>
    </div>
  );
}

export default function LineSelector({ lines, selected, onChange }: Props) {
  const toggle = (code: string) => {
    if (selected.includes(code)) {
      onChange(selected.filter((c) => c !== code));
    } else {
      onChange([...selected, code]);
    }
  };

  const clearAll = () => onChange([]);

  const metroLines = lines.filter((l) => l.mode === "metro");
  const rerLines = lines.filter((l) => l.mode === "rer");
  const transilienLines = lines.filter((l) => l.mode === "transilien");

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

      {metroLines.length > 0 && (
        <LineGroup title="Métro" lines={metroLines} selected={selected} onChange={onChange} onToggle={toggle} />
      )}
      {rerLines.length > 0 && (
        <LineGroup title="RER" lines={rerLines} selected={selected} onChange={onChange} onToggle={toggle} />
      )}
      {transilienLines.length > 0 && (
        <LineGroup title="Transilien" lines={transilienLines} selected={selected} onChange={onChange} onToggle={toggle} />
      )}
    </section>
  );
}
