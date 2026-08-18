/**
 * La préférence « moins de mouvement », lue proprement.
 *
 * `useSyncExternalStore` plutôt qu'un `useEffect` : il évite un `setState` synchrone
 * dans un effet, et surtout il fournit une valeur pour le rendu serveur. Lire
 * `matchMedia` pendant le rendu provoquerait un décalage d'hydratation, puisque le
 * serveur n'a pas de fenêtre.
 */
"use client";

import { useSyncExternalStore } from "react";

const REQUETE = "(prefers-reduced-motion: reduce)";

function abonner(rappel: () => void): () => void {
  const requete = window.matchMedia(REQUETE);
  requete.addEventListener("change", rappel);
  return () => requete.removeEventListener("change", rappel);
}

export function useMouvementReduit(): boolean {
  return useSyncExternalStore(
    abonner,
    () => window.matchMedia(REQUETE).matches,
    // Sur le serveur, on suppose le mouvement autorisé : c'est le cas majoritaire,
    // et la valeur réelle arrive dès l'hydratation.
    () => false,
  );
}
