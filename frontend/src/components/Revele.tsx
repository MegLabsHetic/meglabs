/**
 * Révélation au défilement.
 *
 * L'état de départ est porté par un attribut lu en CSS, pas par React : l'élément
 * est donc déjà masqué au premier rendu, sans le clignotement qu'on obtient quand
 * le script doit d'abord s'exécuter.
 *
 * L'observateur se désabonne dès qu'un bloc est apparu : rien ne doit disparaître
 * en remontant, c'est désagréable et ça n'apporte rien.
 */
"use client";

import { useEffect, useRef } from "react";

export function Revele({
  children,
  delai = 0,
  className = "",
}: {
  children: React.ReactNode;
  /** Décalage en millisecondes, pour faire entrer une série l'une après l'autre. */
  delai?: number;
  className?: string;
}) {
  const bloc = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cible = bloc.current;
    if (!cible) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      cible.dataset.revele = "visible";
      return;
    }

    const observateur = new IntersectionObserver(
      (entrees) => {
        for (const entree of entrees) {
          if (!entree.isIntersecting) continue;
          cible.style.transitionDelay = `${delai}ms`;
          cible.dataset.revele = "visible";
          observateur.disconnect();
        }
      },
      // Le bloc se révèle un peu avant d'être en plein cadre : au moment où le
      // regard y arrive, l'animation est déjà lancée.
      { rootMargin: "0px 0px -12% 0px", threshold: 0.05 },
    );

    observateur.observe(cible);
    return () => observateur.disconnect();
  }, [delai]);

  return (
    <div ref={bloc} data-revele="attente" className={className}>
      {children}
    </div>
  );
}
