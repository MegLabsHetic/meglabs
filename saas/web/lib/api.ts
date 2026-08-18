import { supabase } from "./supabaseClient";
import { fermerSession, lireJeton } from "./session";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
const DEV_USER_ID = process.env.NEXT_PUBLIC_DEV_USER_ID || "";

/**
 * En-tetes d'authentification, par ordre de priorite :
 * 1. jeton de session emis par notre api (mode local) ;
 * 2. JWT Supabase, si le projet est configure ;
 * 3. en-tete de developpement, utile pour les tests sans compte.
 */
async function authHeaders(): Promise<Record<string, string>> {
  const local = lireJeton();
  if (local) return { Authorization: `Bearer ${local}` };

  if (supabase) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) return { Authorization: `Bearer ${token}` };
  }
  if (DEV_USER_ID) return { "x-dev-user-id": DEV_USER_ID };
  return {};
}

/** Session expiree ou revoquee : on nettoie et on renvoie a la connexion. */
function sessionPerdue() {
  if (typeof window === "undefined") return;
  fermerSession();
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login?expiree=1";
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(await authHeaders()),
    ...((options.headers as Record<string, string>) || {}),
  };
  const res = await fetch(`${API}${path}`, { ...options, headers });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (res.status === 401) {
    sessionPerdue();
    throw new Error("Session expirée, reconnectez-vous.");
  }
  if (!res.ok) {
    throw new Error(body?.error || `Erreur ${res.status}`);
  }
  return body as T;
}

/** Appel non authentifie (inscription, connexion). */
export async function apiPublic<T = any>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const texte = await res.text();
  const corps = texte ? JSON.parse(texte) : null;
  if (!res.ok) {
    throw new Error(corps?.error || `Erreur ${res.status}`);
  }
  return corps as T;
}

/**
 * Telecharge un document binaire (le rapport PDF).
 *
 * `apiFetch` parse la reponse en JSON : elle ne convient pas ici. On lit donc
 * le corps en blob et on declenche l'enregistrement cote navigateur.
 */
export async function apiDownload(
  path: string,
  body: unknown,
  fallbackName: string
): Promise<void> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const texte = await res.text();
    let message = `Erreur ${res.status}`;
    try {
      message = JSON.parse(texte)?.error || message;
    } catch {
      /* corps non JSON : on garde le code d'erreur */
    }
    throw new Error(message);
  }

  // Le nom propose par le serveur fait foi quand il est present.
  const dispo = res.headers.get("content-disposition") || "";
  const trouve = /filename="?([^";]+)"?/.exec(dispo);
  const nom = trouve ? trouve[1] : fallbackName;

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Liberer l'objet immediatement annulerait le telechargement dans certains
  // navigateurs : on laisse un court delai.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Langue de l'interface, pour les agents sans question a analyser. */
export function uiLangue(): string {
  if (typeof navigator === "undefined") return "fr";
  const l = (navigator.language || "fr").slice(0, 2).toLowerCase();
  return ["fr", "en", "ar"].includes(l) ? l : "fr";
}

/** Une session est ouverte, d'une maniere ou d'une autre. */
export function isAuthenticatedSync(): boolean {
  return Boolean(lireJeton()) || Boolean(DEV_USER_ID) || Boolean(supabase);
}
