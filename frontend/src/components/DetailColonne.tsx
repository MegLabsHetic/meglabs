/** Le détail d'une colonne : ses statistiques, ses valeurs, ce qui cloche. */
"use client";

import type { Colonne } from "@/lib/types";

const LIBELLES_ANOMALIES: Record<string, string> = {
  formats_multiples: "Formats mélangés",
  valeurs_extremes: "Valeurs extrêmes",
  modalites_variantes: "Modalités variantes",
};

const LIBELLES_STATS: Record<string, string> = {
  minimum: "Minimum",
  maximum: "Maximum",
  moyenne: "Moyenne",
  mediane: "Médiane",
  ecart_type: "Écart-type",
};

function nombre(valeur: number): string {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
}

export function DetailColonne({
  colonne,
  nbLignes,
  onFermer,
}: {
  colonne: Colonne;
  nbLignes: number;
  onFermer: () => void;
}) {
  const stats = colonne.statistiques;
  const numeriques = Object.entries(LIBELLES_STATS).filter(
    ([cle]) => stats[cle as keyof typeof stats] !== undefined,
  );
  const modalites = stats.modalites_frequentes ?? [];

  return (
    <aside
      className="apparait verre p-5"
      aria-label={`Détail de la colonne ${colonne.nom}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-medium">{colonne.nom}</h3>
          <p className="mt-0.5 text-sm" style={{ color: "var(--ink-2)" }}>
            {colonne.type} · {nombre(colonne.cardinalite)} valeur
            {colonne.cardinalite > 1 ? "s" : ""} distincte
            {colonne.cardinalite > 1 ? "s" : ""} sur {nombre(nbLignes)} ligne
            {nbLignes > 1 ? "s" : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={onFermer}
          className="rounded-lg border px-2.5 py-1 text-xs"
          style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
        >
          Fermer
        </button>
      </div>

      {colonne.anomalies.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {colonne.anomalies.map((anomalie) => (
            <li key={anomalie.type} className="flex items-baseline gap-2 text-sm">
              <span aria-hidden style={{ color: "var(--etat-serieux)" }}>
                ▲
              </span>
              <span>
                <span className="font-medium">
                  {LIBELLES_ANOMALIES[anomalie.type] ?? anomalie.type}
                </span>
                <span style={{ color: "var(--ink-2)" }}> — {anomalie.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt style={{ color: "var(--ink-2)" }}>Valeurs absentes</dt>
          <dd className="chiffres-alignes font-medium">
            {nombre(colonne.valeurs_manquantes)}{" "}
            <span className="font-normal" style={{ color: "var(--ink-muted)" }}>
              ({(colonne.part_manquantes * 100).toFixed(1)} %)
            </span>
          </dd>
        </div>
        {numeriques.map(([cle, libelle]) => (
          <div key={cle}>
            <dt style={{ color: "var(--ink-2)" }}>{libelle}</dt>
            <dd className="chiffres-alignes font-medium">
              {nombre(stats[cle as keyof typeof stats] as number)}
            </dd>
          </div>
        ))}
      </dl>

      {modalites.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm" style={{ color: "var(--ink-2)" }}>
            Valeurs les plus fréquentes
          </h4>
          <ul className="mt-2 space-y-1.5">
            {modalites.map((modalite) => (
              <li key={modalite.valeur} className="flex items-center gap-3 text-sm">
                {/* Barre fine, extrémité arrondie, proportionnelle à la plus fréquente. */}
                <div
                  className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full"
                  style={{ background: "var(--accent-piste)" }}
                >
                  <div
                    className="h-full rounded-r-[4px]"
                    style={{
                      width: `${(modalite.occurrences / modalites[0].occurrences) * 100}%`,
                      background: "var(--accent-donnees)",
                    }}
                  />
                </div>
                <span className="min-w-0 flex-1 truncate">{modalite.valeur}</span>
                <span
                  className="chiffres-alignes shrink-0 text-xs"
                  style={{ color: "var(--ink-2)" }}
                >
                  {nombre(modalite.occurrences)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4">
        <h4 className="text-sm" style={{ color: "var(--ink-2)" }}>
          Exemples transmis au modèle
        </h4>
        <p className="mt-1 text-xs" style={{ color: "var(--ink-muted)" }}>
          Trois valeurs au maximum, coupées à 80 caractères. C&apos;est tout ce qui sort
          de ce serveur.
        </p>
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {colonne.exemples.map((exemple, rang) => (
            <li
              key={`${exemple}-${rang}`}
              className="max-w-full truncate rounded-md border px-2 py-0.5 text-xs"
              style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
            >
              {exemple}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
