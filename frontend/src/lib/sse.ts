/**
 * Client Server-Sent Events typé.
 *
 * `EventSource` ne sait pas envoyer de POST ni de corps JSON : on lit donc le flux
 * à la main sur la réponse `fetch`. C'est aussi ce qui permet d'interrompre proprement
 * une réponse en cours, ce qu'`EventSource` ne propose pas.
 *
 * Le protocole vient du backend (`core/events.py`) : un bloc par événement, séparé
 * par une ligne vide, avec une ligne `event:` et une ligne `data:`.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface EvenementAgent {
  agent: string;
  etat: "started" | "working" | "done";
  detail: string;
  duree_ms?: number;
}

export interface EvenementSql {
  sql: string;
  duree_ms: number;
  nb_lignes: number;
  tronque: boolean;
}

export interface EvenementReparation {
  sql_echoue: string;
  erreur: string;
  sql_corrige: string;
  explication: string;
}

export interface AppelTrace {
  agent: string;
  fournisseur: string;
  modele: string;
  tokens_entree: number;
  tokens_sortie: number;
  tokens_caches: number;
  cout_centimes: number;
  economie_centimes: number;
  duree_ms: number;
  tentatives: number;
}

export interface ReponseFinale {
  texte: string;
  intention: string;
  sql: string | null;
  colonnes: string[];
  lignes: (string | number | null)[][];
  tronque: boolean;
  besoin_visualisation: boolean;
  cout_centimes: number;
  depuis_cache: boolean;
  trace: AppelTrace[];
}

export interface Ecouteurs {
  agent?: (evenement: EvenementAgent) => void;
  jeton?: (texte: string) => void;
  sql?: (evenement: EvenementSql) => void;
  reparation?: (evenement: EvenementReparation) => void;
  fin?: (reponse: ReponseFinale) => void;
  erreur?: (message: string) => void;
}

/** Découpe le flux en blocs, en gardant ce qui n'est pas encore complet. */
function* blocs(tampon: { reste: string }, morceau: string): Generator<string> {
  tampon.reste += morceau;
  let coupure = tampon.reste.indexOf("\n\n");
  while (coupure !== -1) {
    yield tampon.reste.slice(0, coupure);
    tampon.reste = tampon.reste.slice(coupure + 2);
    coupure = tampon.reste.indexOf("\n\n");
  }
}

function distribuer(bloc: string, ecouteurs: Ecouteurs): void {
  const type = /^event: (.+)$/m.exec(bloc)?.[1];
  const brut = /^data: (.*)$/m.exec(bloc)?.[1];
  if (!type || brut === undefined) return;

  let donnees: unknown;
  try {
    donnees = JSON.parse(brut);
  } catch {
    // Un bloc illisible ne doit pas faire tomber la conversation entière.
    return;
  }

  switch (type) {
    case "agent_status":
      ecouteurs.agent?.(donnees as EvenementAgent);
      break;
    case "token":
      ecouteurs.jeton?.((donnees as { texte: string }).texte);
      break;
    case "sql":
      ecouteurs.sql?.(donnees as EvenementSql);
      break;
    case "sql_healing":
      ecouteurs.reparation?.(donnees as EvenementReparation);
      break;
    case "done":
      ecouteurs.fin?.(donnees as ReponseFinale);
      break;
    case "erreur":
      ecouteurs.erreur?.((donnees as { message: string }).message);
      break;
  }
}

export async function poserQuestion(
  espaceId: string,
  question: string,
  ecouteurs: Ecouteurs,
  signal?: AbortSignal,
): Promise<void> {
  let reponse: Response;
  try {
    reponse = await fetch(`${BASE}/api/chat/${espaceId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch {
    ecouteurs.erreur?.(
      "Le serveur ne répond pas. Vérifie qu'il est démarré et qu'il autorise " +
        `l'origine ${typeof window === "undefined" ? "" : window.location.origin}.`,
    );
    return;
  }

  if (!reponse.ok || !reponse.body) {
    ecouteurs.erreur?.("Le serveur n'a pas pu traiter la demande.");
    return;
  }

  const lecteur = reponse.body.getReader();
  const decodeur = new TextDecoder();
  const tampon = { reste: "" };

  while (true) {
    const { done, value } = await lecteur.read();
    if (done) break;
    for (const bloc of blocs(tampon, decodeur.decode(value, { stream: true }))) {
      distribuer(bloc, ecouteurs);
    }
  }
}
