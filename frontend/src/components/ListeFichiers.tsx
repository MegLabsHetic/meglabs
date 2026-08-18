/** Les fichiers d'un espace de travail, et celui sur lequel on travaille. */
"use client";

import type { Fichier, StatutPii } from "@/lib/types";

const ETATS_PII: Record<StatutPii, { icone: string; couleur: string; libelle: string }> = {
  aucune: { icone: "●", couleur: "var(--etat-bon)", libelle: "Rien à protéger" },
  detectee: { icone: "▲", couleur: "var(--etat-attention)", libelle: "À pseudonymiser" },
  masquee: { icone: "●", couleur: "var(--etat-bon)", libelle: "Pseudonymisé" },
};

function taille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(0)} ko`;
  return `${(octets / 1024 / 1024).toFixed(1)} Mo`;
}

export function ListeFichiers({
  fichiers,
  selection,
  onChoisir,
}: {
  fichiers: Fichier[];
  selection: Fichier | null;
  onChoisir: (fichier: Fichier) => void;
}) {
  if (fichiers.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>
        {fichiers.length} fichier{fichiers.length > 1 ? "s" : ""} dans cet espace
      </h2>

      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {fichiers.map((fichier) => {
          const etat = ETATS_PII[fichier.statut_pii];
          const choisi = fichier.id === selection?.id;
          return (
            <li key={fichier.id}>
              <button
                type="button"
                onClick={() => onChoisir(fichier)}
                aria-pressed={choisi}
                className="w-full rounded-xl border p-3 text-left transition-colors"
                style={{
                  background: "var(--panneau)",
                  borderColor: choisi ? "var(--accent-donnees)" : "var(--filet)",
                  boxShadow: choisi ? "inset 0 0 0 1px var(--accent-donnees)" : undefined,
                }}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm font-medium">{fichier.nom}</span>
                  <span
                    className="chiffres-alignes shrink-0 text-xs"
                    style={{ color: "var(--ink-muted)" }}
                  >
                    {fichier.score_qualite?.toFixed(1) ?? "—"}
                  </span>
                </div>
                <div
                  className="mt-1 flex items-center gap-2 text-xs"
                  style={{ color: "var(--ink-2)" }}
                >
                  <span aria-hidden style={{ color: etat.couleur }}>
                    {etat.icone}
                  </span>
                  <span>{etat.libelle}</span>
                  <span aria-hidden style={{ color: "var(--ink-muted)" }}>
                    ·
                  </span>
                  <span>{taille(fichier.taille_octets)}</span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
