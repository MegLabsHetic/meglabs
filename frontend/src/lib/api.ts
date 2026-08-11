/**
 * Client HTTP du backend.
 *
 * Les erreurs métier arrivent avec un message français déjà rédigé pour
 * l'utilisateur : on le remonte tel quel plutôt que d'en inventer un.
 */

import type { Depot, Profil, Pseudonymisation, Workspace } from "./types";

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
    throw new ErreurApi(
      "Le serveur ne répond pas. Vérifie qu'il est démarré, puis réessaie.",
    );
  }
}

export const api = {
  creerWorkspace: (nom: string) =>
    appeler<Workspace>("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nom }),
    }),

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
};
