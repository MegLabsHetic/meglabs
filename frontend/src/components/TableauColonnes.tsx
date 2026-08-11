/**
 * Le profil colonne par colonne.
 *
 * Le type n'est pas un état, seulement une forme : il porte donc une pastille
 * neutre, pas une couleur d'identité. La couleur est réservée à ce qui demande
 * une décision — le taux de valeurs manquantes et les anomalies.
 */
import type { Colonne } from "@/lib/types";

const LIBELLES_ANOMALIES: Record<string, string> = {
  formats_multiples: "Formats mélangés",
  valeurs_extremes: "Valeurs extrêmes",
  modalites_variantes: "Modalités variantes",
};

function resume(colonne: Colonne): string {
  const stats = colonne.statistiques;
  if (stats.moyenne !== undefined) {
    return `moyenne ${stats.moyenne.toLocaleString("fr-FR")} · de ${stats.minimum?.toLocaleString("fr-FR")} à ${stats.maximum?.toLocaleString("fr-FR")}`;
  }
  const modalites = stats.modalites_frequentes;
  if (modalites?.length) {
    return modalites
      .slice(0, 3)
      .map((m) => m.valeur)
      .join(" · ");
  }
  return colonne.exemples.slice(0, 3).join(" · ");
}

function BarreManquantes({ part }: { part: number }) {
  const pourcentage = part * 100;
  return (
    <div className="flex items-center gap-2">
      {/* Barre fine, extrémité arrondie, ancrée à sa base. */}
      <div
        className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full"
        style={{ background: "var(--mesure-piste)" }}
      >
        <div
          className="h-full rounded-r-[4px]"
          style={{
            width: `${Math.min(100, Math.max(part > 0 ? 4 : 0, pourcentage))}%`,
            background: "var(--mesure)",
          }}
        />
      </div>
      <span
        className="chiffres-alignes w-11 text-right text-xs"
        style={{ color: part > 0 ? "var(--ink-2)" : "var(--ink-muted)" }}
      >
        {pourcentage.toFixed(1)} %
      </span>
    </div>
  );
}

export function TableauColonnes({ colonnes }: { colonnes: Colonne[] }) {
  return (
    <div>
      <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>
        Les {colonnes.length} colonnes
      </h2>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr
              className="text-left text-xs"
              style={{ color: "var(--ink-muted)" }}
            >
              <th className="pb-2 font-normal">Colonne</th>
              <th className="pb-2 font-normal">Type</th>
              <th className="pb-2 font-normal">Valeurs absentes</th>
              <th className="pb-2 text-right font-normal">Valeurs distinctes</th>
              <th className="pb-2 pl-4 font-normal">Aperçu</th>
            </tr>
          </thead>
          <tbody>
            {colonnes.map((colonne) => (
              <tr
                key={colonne.nom}
                className="border-t align-top"
                style={{ borderColor: "var(--hairline)" }}
              >
                <td className="py-2.5 pr-4">
                  <div className="font-medium">{colonne.nom}</div>
                  {colonne.anomalies.map((anomalie) => (
                    <div
                      key={anomalie.type}
                      className="mt-1 flex items-baseline gap-1.5 text-xs"
                    >
                      <span aria-hidden style={{ color: "var(--etat-serieux)" }}>
                        ▲
                      </span>
                      <span style={{ color: "var(--ink-2)" }}>
                        <span className="font-medium">
                          {LIBELLES_ANOMALIES[anomalie.type] ?? anomalie.type}
                        </span>{" "}
                        — {anomalie.detail}
                      </span>
                    </div>
                  ))}
                </td>
                <td className="py-2.5 pr-4">
                  <span
                    className="rounded-md border px-1.5 py-0.5 text-xs"
                    style={{ borderColor: "var(--bordure)", color: "var(--ink-2)" }}
                  >
                    {colonne.type}
                  </span>
                </td>
                <td className="py-2.5 pr-4">
                  <BarreManquantes part={colonne.part_manquantes} />
                </td>
                <td className="chiffres-alignes py-2.5 pr-4 text-right">
                  {colonne.cardinalite.toLocaleString("fr-FR")}
                </td>
                <td
                  className="max-w-[280px] truncate py-2.5 pl-4 text-xs"
                  style={{ color: "var(--ink-2)" }}
                  title={resume(colonne)}
                >
                  {resume(colonne)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
