/**
 * Tuile de statistique.
 *
 * Deux détails qui font la différence entre « joli » et « fini » :
 *  - la valeur monte jusqu'à son chiffre au lieu d'apparaître, ce qui attire l'œil
 *    là où il faut lire ;
 *  - la tuile s'incline légèrement sous le curseur, ce qui donne l'épaisseur sans
 *    ombre portée grossière.
 *
 * Les grands nombres isolés gardent les chiffres proportionnels : les chiffres
 * tabulaires donnent à chaque caractère la largeur d'un zéro, ce qui fait flotter
 * un nombre affiché en grand.
 */
"use client";

import { useEffect, useRef, useState } from "react";

import { useMouvementReduit } from "@/lib/mouvement";

const DUREE = 700;

/** Avancement de 0 à 1. L'état n'est écrit que depuis une image d'animation. */
function useAvancement(actif: boolean, cible: number): number {
  const [avancement, setAvancement] = useState(0);

  useEffect(() => {
    if (!actif) return;

    let animation = 0;
    const debut = performance.now();
    const avancer = (maintenant: number) => {
      const part = Math.min((maintenant - debut) / DUREE, 1);
      setAvancement(part);
      if (part < 1) animation = requestAnimationFrame(avancer);
    };
    animation = requestAnimationFrame(avancer);
    return () => cancelAnimationFrame(animation);
  }, [actif, cible]);

  return avancement;
}

export function TuileStat({
  libelle,
  valeur,
  precision,
  nombre,
  decimales = 0,
}: {
  libelle: string;
  valeur: string;
  precision?: string;
  /** Fourni pour animer la montée. Sinon `valeur` est affichée telle quelle. */
  nombre?: number;
  decimales?: number;
}) {
  const mouvementReduit = useMouvementReduit();
  const anime = nombre !== undefined && !mouvementReduit;
  const avancement = useAvancement(anime, nombre ?? 0);
  const carte = useRef<HTMLDivElement>(null);

  // Sortie douce : rapide au début, freine à l'arrivée.
  const affiche =
    nombre === undefined ? null : anime ? nombre * (1 - (1 - avancement) ** 3) : nombre;

  const incliner = (evenement: React.MouseEvent<HTMLDivElement>) => {
    const cible = carte.current;
    if (!cible || mouvementReduit) return;
    const cadre = cible.getBoundingClientRect();
    const x = (evenement.clientX - cadre.left) / cadre.width - 0.5;
    const y = (evenement.clientY - cadre.top) / cadre.height - 0.5;
    cible.style.transform = `perspective(700px) rotateX(${-y * 5}deg) rotateY(${x * 5}deg) translateZ(6px)`;
  };

  const redresser = () => {
    if (carte.current) carte.current.style.transform = "";
  };

  return (
    <div
      ref={carte}
      onMouseMove={incliner}
      onMouseLeave={redresser}
      className="verre px-4 py-3.5 transition-transform duration-200 will-change-transform"
    >
      <div className="text-[12px] uppercase tracking-wider" style={{ color: "var(--ink-muted)" }}>
        {libelle}
      </div>
      <div
        className="mt-1.5 text-3xl font-semibold tracking-tight"
        style={{ color: "var(--ink-1)" }}
      >
        {affiche === null
          ? valeur
          : affiche.toLocaleString("fr-FR", {
              minimumFractionDigits: decimales,
              maximumFractionDigits: decimales,
            })}
      </div>
      {precision && (
        <div className="mt-1 text-xs" style={{ color: "var(--ink-3)" }}>
          {precision}
        </div>
      )}
    </div>
  );
}
