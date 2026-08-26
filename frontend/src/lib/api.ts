/**
 * Client HTTP du backend.
 *
 * Les erreurs métier arrivent avec un message français déjà rédigé pour
 * l'utilisateur : on le remonte tel quel plutôt que d'en inventer un.
 */

import type { Proposition } from "@/components/Nettoyage";

import type {
  Depot,
  Detection,
  Fichier,
  Profil,
  Pseudonymisation,
  Rapport,
  Workspace,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ErreurApi extends Error {}

async function lire<T>(reponse: Response): Promise<T> {
  if (reponse.ok) return (await reponse.json()) as T;

  let message = "Le serveur n'a pas pu traiter la demande.";
  try {
    const corps = await reponse.json();
    if (typeof corps?.detail === "string") message = corps.detail;
  } catch {
    // Réponse sans corps JSON : le message par défaut fera l'affaire.
  }
  throw new ErreurApi(message);
}

async function appeler<T>(chemin: string, init?: RequestInit): Promise<T> {
  try {
    return await lire<T>(await fetch(`${BASE}${chemin}`, init));
  } catch (erreur) {
    if (erreur instanceof ErreurApi) throw erreur;
    // Le navigateur ne dit pas si `fetch` a échoué faute de serveur ou parce que
    // l'origine a été refusée : les deux se présentent comme une erreur réseau.
    // Le message doit donc couvrir les deux, sinon il envoie chercher au mauvais
    // endroit — c'est arrivé en changeant le port du front sans toucher CORS.
    throw new ErreurApi(
      `Impossible de joindre le serveur sur ${BASE}. Vérifie qu'il est démarré, ` +
        `et que ${origineCourante()} figure bien dans CORS_ORIGINS côté serveur.`,
    );
  }
}

function origineCourante(): string {
  return typeof window === "undefined" ? "l'origine du site" : window.location.origin;
}

export const api = {
  creerWorkspace: (nom: string) =>
    appeler<Workspace>("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nom }),
    }),

  listerWorkspaces: () => appeler<Workspace[]>("/api/workspaces"),

  recupererWorkspace: (id: string) => appeler<Workspace>(`/api/workspaces/${id}`),

  listerFichiers: (workspaceId: string) =>
    appeler<Fichier[]>(`/api/workspaces/${workspaceId}/files`),

  donneesPersonnelles: (fichierId: string) =>
    appeler<Detection[]>(`/api/files/${fichierId}/pii`),

  deposer: (workspaceId: string, fichier: File) => {
    const corps = new FormData();
    corps.append("fichier", fichier);
    return appeler<Depot>(`/api/workspaces/${workspaceId}/files`, {
      method: "POST",
      body: corps,
    });
  },

  pseudonymiser: (fichierId: string) =>
    appeler<Pseudonymisation>(`/api/files/${fichierId}/pseudonymise`, {
      method: "POST",
    }),

  profil: (fichierId: string) => appeler<Profil>(`/api/files/${fichierId}/profile`),

  /** Le rapport de l espace : sources, corrections, questions, score. */
  rapport: (workspaceId: string) => appeler<Rapport>(`/api/workspaces/${workspaceId}/rapport`),

  /** Les corrections que les defauts detectes justifient, avec leur impact. */
  propositionsNettoyage: (fichierId: string) =>
    appeler<Proposition[]>(`/api/files/${fichierId}/nettoyage`),

  /** Applique les corrections choisies et rend le nouveau profil. */
  nettoyer: (fichierId: string, types: string[]) =>
    appeler<Depot>(`/api/files/${fichierId}/nettoyage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ types }),
    }),
};
