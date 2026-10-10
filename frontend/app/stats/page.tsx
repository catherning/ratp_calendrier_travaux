"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { CategoryCount, DisruptionStatistics } from "@/lib/types";
import { causeLabel, effectLabel } from "@/lib/utils";
import styles from "./stats.module.css";

function Breakdown({ title, items, total, label }: {
  title: string;
  items: CategoryCount[];
  total: number;
  label: (type: string) => string;
}) {
  return (
    <section className="card panel">
      <h2 className="panel__title">{title}</h2>
      {items.length === 0 ? <p>Aucune perturbation recensée.</p> : (
        <ul className={styles.breakdown}>
          {items.map((item) => (
            <li key={item.type}>
              <div className={styles.row}>
                <span>{item.type === "unknown" ? "Non renseigné" : label(item.type)}</span>
                <strong>{item.count} ({Math.round(item.count / total * 100)} %)</strong>
              </div>
              <div className={styles.bar} aria-hidden="true">
                <div style={{ width: `${item.count / total * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function StatisticsPage() {
  const [data, setData] = useState<DisruptionStatistics | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    api.getStatistics().then((result) => {
      if (active) setData(result);
    }).catch((err: unknown) => {
      console.error("Failed to load network statistics:", err);
      if (active) setError(true);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [retry]);

  function reload() {
    setLoading(true);
    setError(false);
    setData(null);
    setRetry((value) => value + 1);
  }

  return (
    <main className="app-container">
      <header className={`app-header ${styles.header}`}>
        <div>
          <h1 className="app-header__title">Statistiques du réseau</h1>
          <p className="app-header__subtitle">Métro, RER et Transilien · Toutes les lignes prises en charge</p>
        </div>
        <Link href="/" className="btn btn--secondary">Retour aux perturbations</Link>
      </header>

      <p className={styles.note}>
        Perturbations retenues par le PoC, en cours ou à venir, sans filtre de ligne ni d’itinéraire.
        Chaque impact est compté une seule fois, même s’il comporte plusieurs périodes ou touche plusieurs lignes.
        Il ne s’agit pas d’un historique.
      </p>

      {loading && <div className="state-message state-message--loading" role="status">
        <div className="loader" /><p>Chargement des statistiques de toutes les lignes…</p>
      </div>}
      {error && <div className="state-message" role="alert">
        <p>Impossible de charger les statistiques du réseau.</p>
        <button className="btn btn--secondary" onClick={reload}>Réessayer</button>
      </div>}

      {data && !loading && !error && <>
        {data.failed_lines.length > 0 && <section className={`card panel ${styles.warning}`} role="alert">
          <strong>Données partielles</strong>
          <p>Lignes indisponibles : {data.failed_lines.join(", ")}. Elles sont exclues des totaux et ne sont pas comptées comme sans perturbation.</p>
          <button className="btn btn--secondary" onClick={reload}>Réessayer</button>
        </section>}

        <section className={styles.metrics} aria-label="Chiffres clés">
          {[
            ["Perturbations uniques", data.total_disruptions],
            ["Lignes avec perturbations", data.lines_with_disruptions],
            ["Lignes sans perturbation", data.lines_without_disruptions],
            ["Lignes indisponibles", data.failed_lines.length],
          ].map(([label, value]) => <div className={`card panel ${styles.metric}`} key={label}>
            <span>{label}</span><strong>{value}</strong>
          </div>)}
        </section>

        <p className={styles.note}>
          {data.total_lines - data.failed_lines.length} / {data.total_lines} lignes consultées.
          {" "}Calculé le {new Date(data.generated_at).toLocaleString("fr-FR", { timeZone: "Europe/Paris" })} (heure de Paris).
          Les données Navitia sont mises en cache jusqu’à 5 minutes.
        </p>

        <div className={styles.columns}>
          <section className="card panel">
            <h2 className="panel__title">Classement des lignes</h2>
            <p className={styles.note}>Un même impact peut figurer sur plusieurs lignes : la somme peut dépasser le total unique.</p>
            <div className={styles.tableContainer}>
              <table className={styles.table}>
                <caption className={styles.note}>Toutes les lignes, par nombre décroissant de perturbations</caption>
                <thead><tr><th scope="col">Ligne</th><th scope="col">Perturbations</th></tr></thead>
                <tbody>{data.lines.map((line) => <tr key={line.code}>
                  <th scope="row">
                    <span className={styles.lineBadge} style={{ background: `#${line.color}`, color: `#${line.text_color}` }}>{line.code}</span>
                    {line.name}
                  </th>
                  <td>{line.disruption_count ?? "Indisponible"}</td>
                </tr>)}</tbody>
              </table>
            </div>
          </section>
          <div className={styles.categories}>
            <Breakdown title="Types d’impact" items={data.effects} total={data.total_disruptions} label={effectLabel} />
            <Breakdown title="Causes des perturbations" items={data.causes} total={data.total_disruptions} label={causeLabel} />
          </div>
        </div>
      </>}
    </main>
  );
}
