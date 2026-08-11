/**
 * Jauge de qualité, avec le détail de ce qui l'a fait baisser.
 *
 * La couleur ne porte jamais le sens seule : les états « bon » et « faible » ne
 * sont séparés que de ΔE 4.1 en deutéranopie. Un libellé et une icône
 * accompagnent donc toujours la barre.
 */
import type { Penalite } from "@/lib/types";

interface Etat {
  libelle: string;
  icone: string;
  couleur: string;
}

function etatDuScore(score: number): Etat {
  if (score >= 90) return { libelle: "Bonne qualité", icone: "●", couleur: "var(--etat-bon)" };
  if (score >= 70)
    return { libelle: "À surveiller", icone: "▲", couleur: "var(--etat-attention)" };
  return { libelle: "Qualité faible", icone: "■", couleur: "var(--etat-faible)" };
}

export function ScoreQualite({
  score,
  explication,
}: {
  score: number;
  explication: Penalite[];
}) {
  const etat = etatDuScore(score);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>
          Qualité des données
        </h2>
        <div className="flex items-center gap-2 text-sm">
          <span aria-hidden style={{ color: etat.couleur }}>
            {etat.icone}
          </span>
          <span style={{ color: "var(--ink-2)" }}>{etat.libelle}</span>
        </div>
      </div>

      <div className="mt-3 flex items-end gap-3">
        <span className="text-4xl font-semibold leading-none tracking-tight">
          {score.toFixed(1)}
        </span>
        <span className="pb-1 text-sm" style={{ color: "var(--ink-muted)" }}>
          sur 100
        </span>
      </div>

      {/* La piste est une teinte claire de la même couleur : l'état se lit sur
          toute la largeur de la barre, pas seulement sur la partie remplie. */}
      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full"
        style={{ background: `color-mix(in oklab, ${etat.couleur} 18%, var(--surface-1))` }}
        role="img"
        aria-label={`Score de qualité : ${score.toFixed(1)} sur 100. ${etat.libelle}.`}
      >
        <div
          className="h-full rounded-r-[4px] transition-[width] duration-700 ease-out"
          style={{ width: `${Math.max(2, score)}%`, background: etat.couleur }}
        />
      </div>

      {explication.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {explication.map((penalite) => (
            <li key={penalite.critere} className="flex gap-3 text-sm">
              <span
                className="chiffres-alignes shrink-0 pt-px font-medium"
                style={{ color: "var(--ink-2)" }}
              >
                {penalite.impact.toFixed(1)}
              </span>
              <span>
                <span className="font-medium">{penalite.critere}</span>
                <span style={{ color: "var(--ink-2)" }}> — {penalite.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm" style={{ color: "var(--ink-2)" }}>
          Aucun défaut détecté : pas de valeurs manquantes, pas de doublons, pas
          d&apos;incohérence de saisie.
        </p>
      )}
    </div>
  );
}
