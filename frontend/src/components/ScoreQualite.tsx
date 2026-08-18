/**
 * Jauge de qualité en arc, avec le détail de ce qui l'a fait baisser.
 *
 * La couleur ne porte jamais le sens seule : mesuré, les états « bon » et « faible »
 * ne sont séparés que de ΔE 6.5 en deutéranopie. Un libellé et une icône
 * accompagnent donc toujours l'arc.
 *
 * L'arc est en SVG et non en CSS : il faut la même géométrie exacte pour la piste et
 * pour le remplissage, et un dégradé qui suit la courbe.
 */
"use client";

import { useEffect, useState } from "react";

import { useMouvementReduit } from "@/lib/mouvement";
import type { Penalite } from "@/lib/types";

const RAYON = 78;
const EPAISSEUR = 12;
// Trois quarts de tour : l'ouverture en bas laisse la place au chiffre.
const ARC = 1.5 * Math.PI;
const LONGUEUR = ARC * RAYON;

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

export function ScoreQualite({ score, explication }: { score: number; explication: Penalite[] }) {
  const etat = etatDuScore(score);
  const mouvementReduit = useMouvementReduit();
  const [monte, setMonte] = useState(false);

  useEffect(() => {
    // Une image d'attente avant de remplir : sans elle, la transition CSS part
    // déjà à sa valeur finale et l'arc apparaît d'un coup.
    const attente = requestAnimationFrame(() => setMonte(true));
    return () => cancelAnimationFrame(attente);
  }, [score]);

  const remplissage = mouvementReduit || monte ? score : 0;

  const taille = RAYON * 2 + EPAISSEUR * 2;
  const centre = taille / 2;

  return (
    <div className="flex flex-wrap items-center gap-8">
      <div className="relative shrink-0" style={{ width: taille, height: taille }}>
        <svg
          width={taille}
          height={taille}
          viewBox={`0 0 ${taille} ${taille}`}
          role="img"
          aria-label={`Score de qualité : ${score.toFixed(1)} sur 100. ${etat.libelle}.`}
          /* L'arc démarre en bas à gauche et tourne vers le bas à droite. */
          style={{ transform: "rotate(135deg)" }}
        >
          <circle
            cx={centre}
            cy={centre}
            r={RAYON}
            fill="none"
            stroke="var(--accent-piste)"
            strokeWidth={EPAISSEUR}
            strokeLinecap="round"
            strokeDasharray={`${LONGUEUR} ${LONGUEUR * 3}`}
          />
          <circle
            cx={centre}
            cy={centre}
            r={RAYON}
            fill="none"
            stroke={etat.couleur}
            strokeWidth={EPAISSEUR}
            strokeLinecap="round"
            strokeDasharray={`${(LONGUEUR * remplissage) / 100} ${LONGUEUR * 3}`}
            style={{
              transition: "stroke-dasharray 900ms var(--sortie)",
              filter: `drop-shadow(0 0 10px ${etat.couleur})`,
            }}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-semibold tracking-tight" style={{ color: "var(--ink-1)" }}>
            {score.toFixed(1)}
          </span>
          <span className="text-xs" style={{ color: "var(--ink-muted)" }}>
            sur 100
          </span>
        </div>
      </div>

      <div className="min-w-60 flex-1">
        <div className="flex items-baseline justify-between gap-4">
          <h2
            className="text-xs uppercase tracking-wider"
            style={{ color: "var(--ink-muted)" }}
          >
            Qualité des données
          </h2>
          <span className="flex items-center gap-2 text-sm">
            <span aria-hidden style={{ color: etat.couleur }}>
              {etat.icone}
            </span>
            <span style={{ color: "var(--ink-2)" }}>{etat.libelle}</span>
          </span>
        </div>

        {explication.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {explication.map((penalite) => (
              <li key={penalite.critere} className="flex gap-3 text-sm">
                <span
                  className="chiffres-alignes shrink-0 pt-px font-medium tabular-nums"
                  style={{ color: "var(--etat-faible)" }}
                >
                  {penalite.impact.toFixed(1)}
                </span>
                <span>
                  <span className="font-medium" style={{ color: "var(--ink-1)" }}>
                    {penalite.critere}
                  </span>
                  <span style={{ color: "var(--ink-3)" }}> — {penalite.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm" style={{ color: "var(--ink-3)" }}>
            Aucun défaut détecté : pas de valeurs manquantes, pas de doublons, pas
            d&apos;incohérence de saisie.
          </p>
        )}
      </div>
    </div>
  );
}
