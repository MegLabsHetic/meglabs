/**
 * Le profil colonne par colonne, avec recherche et tri.
 *
 * Le type n'est pas un état, seulement une forme : il porte donc une pastille
 * neutre, pas une couleur d'identité. La couleur est réservée à ce qui demande
 * une décision — le taux de valeurs absentes et les anomalies.
 */
"use client";

import { useMemo, useState } from "react";

import type { Colonne } from "@/lib/types";

const LIBELLES_ANOMALIES: Record<string, string> = {
  formats_multiples: "Formats mélangés",
  valeurs_extremes: "Valeurs extrêmes",
  modalites_variantes: "Modalités variantes",
};

type Tri = "fichier" | "manquantes" | "cardinalite" | "nom";

const TRIS: { cle: Tri; libelle: string }[] = [
  { cle: "fichier", libelle: "Ordre du fichier" },
  { cle: "manquantes", libelle: "Plus de valeurs absentes" },
  { cle: "cardinalite", libelle: "Plus de valeurs distinctes" },
  { cle: "nom", libelle: "Nom" },
];

function resume(colonne: Colonne): string {
  const stats = colonne.statistiques;
  if (stats.moyenne !== undefined) {
    return `moyenne ${stats.moyenne.toLocaleString("fr-FR")} · de ${stats.minimum?.toLocaleString("fr-FR")} à ${stats.maximum?.toLocaleString("fr-FR")}`;
  }
  const modalites = stats.modalites_frequentes;
  if (modalites?.length) return modalites.slice(0, 3).map((m) => m.valeur).join(" · ");
  return colonne.exemples.slice(0, 3).join(" · ");
}

function BarreManquantes({ part }: { part: number }) {
  const pourcentage = part * 100;
  return (
    <div className="flex items-center gap-2">
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

export function TableauColonnes({
  colonnes,
  selection,
  onSelectionner,
}: {
  colonnes: Colonne[];
  selection: string | null;
  onSelectionner: (nom: string) => void;
}) {
  const [recherche, setRecherche] = useState("");
  const [tri, setTri] = useState<Tri>("fichier");
  const [seulementProblemes, setSeulementProblemes] = useState(false);

  const affichees = useMemo(() => {
    const terme = recherche.trim().toLowerCase();
    const filtrees = colonnes.filter((colonne) => {
      if (terme && !colonne.nom.toLowerCase().includes(terme)) return false;
      if (seulementProblemes && colonne.anomalies.length === 0 && colonne.part_manquantes === 0) {
        return false;
      }
      return true;
    });

    const ordonnees = [...filtrees];
    if (tri === "manquantes") ordonnees.sort((a, b) => b.part_manquantes - a.part_manquantes);
    if (tri === "cardinalite") ordonnees.sort((a, b) => b.cardinalite - a.cardinalite);
    if (tri === "nom") ordonnees.sort((a, b) => a.nom.localeCompare(b.nom, "fr"));
    return ordonnees;
  }, [colonnes, recherche, tri, seulementProblemes]);

  const problematiques = colonnes.filter(
    (colonne) => colonne.anomalies.length > 0 || colonne.part_manquantes > 0,
  ).length;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>
          {affichees.length === colonnes.length
            ? `Les ${colonnes.length} colonnes`
            : `${affichees.length} colonne${affichees.length > 1 ? "s" : ""} sur ${colonnes.length}`}
        </h2>

        <div className="flex flex-wrap items-center gap-2">
          <input
            value={recherche}
            onChange={(evenement) => setRecherche(evenement.target.value)}
            placeholder="Rechercher une colonne"
            aria-label="Rechercher une colonne"
            className="w-48 rounded-lg border px-2.5 py-1.5 text-sm outline-none"
            style={{ borderColor: "var(--bordure)", background: "var(--plan)" }}
          />
          <select
            value={tri}
            onChange={(evenement) => setTri(evenement.target.value as Tri)}
            aria-label="Trier les colonnes"
            className="rounded-lg border px-2.5 py-1.5 text-sm outline-none"
            style={{ borderColor: "var(--bordure)", background: "var(--plan)" }}
          >
            {TRIS.map((option) => (
              <option key={option.cle} value={option.cle}>
                {option.libelle}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setSeulementProblemes((actuel) => !actuel)}
            aria-pressed={seulementProblemes}
            className="rounded-lg border px-2.5 py-1.5 text-sm transition-colors"
            style={{
              borderColor: seulementProblemes ? "var(--mesure)" : "var(--bordure)",
              color: seulementProblemes ? "var(--ink-1)" : "var(--ink-2)",
            }}
          >
            À corriger ({problematiques})
          </button>
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs" style={{ color: "var(--ink-muted)" }}>
              <th className="pb-2 font-normal">Colonne</th>
              <th className="pb-2 font-normal">Type</th>
              <th className="pb-2 font-normal">Valeurs absentes</th>
              <th className="pb-2 text-right font-normal">Valeurs distinctes</th>
              <th className="pb-2 pl-4 font-normal">Aperçu</th>
            </tr>
          </thead>
          <tbody>
            {affichees.map((colonne) => (
              <tr
                key={colonne.nom}
                onClick={() => onSelectionner(colonne.nom)}
                className="cursor-pointer border-t align-top transition-colors"
                style={{
                  borderColor: "var(--hairline)",
                  background:
                    selection === colonne.nom
                      ? "color-mix(in oklab, var(--mesure) 7%, transparent)"
                      : undefined,
                }}
              >
                <td className="py-2.5 pr-4">
                  <div className="font-medium">{colonne.nom}</div>
                  {colonne.anomalies.map((anomalie) => (
                    <div key={anomalie.type} className="mt-1 flex items-baseline gap-1.5 text-xs">
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

        {affichees.length === 0 && (
          <p className="py-6 text-center text-sm" style={{ color: "var(--ink-2)" }}>
            Aucune colonne ne correspond à cette recherche.
          </p>
        )}
      </div>
    </div>
  );
}
