/**
 * Session locale : jeton emis par notre propre api.
 *
 * Le jeton vit dans localStorage. C'est un choix assume et non le plus sur :
 * un cookie httpOnly serait a l'abri d'un script injecte. Il faudrait pour
 * cela que l'api et l'interface partagent un domaine et posent le cookie —
 * a faire au moment de la mise en ligne, ou le domaine est connu.
 */

const CLE_JETON = "datavox.token";
const CLE_UTILISATEUR = "datavox.user";

export type Utilisateur = {
  id: string;
  email: string;
  name?: string | null;
};

export function lireJeton(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(CLE_JETON);
}

export function lireUtilisateur(): Utilisateur | null {
  if (typeof window === "undefined") return null;
  const brut = window.localStorage.getItem(CLE_UTILISATEUR);
  if (!brut) return null;
  try {
    return JSON.parse(brut) as Utilisateur;
  } catch {
    return null;
  }
}

export function ouvrirSession(jeton: string, utilisateur: Utilisateur) {
  window.localStorage.setItem(CLE_JETON, jeton);
  window.localStorage.setItem(CLE_UTILISATEUR, JSON.stringify(utilisateur));
}

export function fermerSession() {
  window.localStorage.removeItem(CLE_JETON);
  window.localStorage.removeItem(CLE_UTILISATEUR);
}
