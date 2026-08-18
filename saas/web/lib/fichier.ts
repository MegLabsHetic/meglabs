/**
 * Preparation d'un fichier avant envoi.
 *
 * Un CSV part en texte, un classeur Excel en base64 : le .xlsx est une
 * archive binaire, `file.text()` la corromprait silencieusement.
 */

export const EXTENSIONS_ACCEPTEES = ".csv,.xlsx,.xls,.txt,.tsv";

/**
 * Taille maximale d'un fichier importable.
 *
 * L'api plafonne les corps de requete a 32 Mo et un binaire voyage encode en
 * base64, ce qui l'alourdit d'un tiers : 24 Mo de fichier est donc le vrai
 * plafond. On le verifie AVANT de lire le fichier, sinon l'utilisateur
 * attendrait l'encodage complet pour recevoir un « 413 » incomprehensible.
 */
export const TAILLE_MAX_OCTETS = 24 * 1024 * 1024;

export function tailleLisible(octets: number): string {
  if (octets >= 1024 * 1024) return `${(octets / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
  return `${Math.round(octets / 1024)} ko`;
}

/** Renvoie un message d'erreur si le fichier est trop lourd, sinon null. */
export function verifierTaille(fichier: File): string | null {
  if (fichier.size <= TAILLE_MAX_OCTETS) return null;
  return (
    `« ${fichier.name} » pèse ${tailleLisible(fichier.size)}, la limite est de ` +
    `${tailleLisible(TAILLE_MAX_OCTETS)}. Découpez le fichier, ou n'exportez que ` +
    `les colonnes utiles.`
  );
}

export type Charge = {
  filename: string;
  csv_text?: string;
  file_base64?: string;
};

const EXTENSIONS_CLASSEUR = [".xlsx", ".xls", ".xlsm"];

function estClasseur(nom: string): boolean {
  const n = nom.toLowerCase();
  return EXTENSIONS_CLASSEUR.some((e) => n.endsWith(e));
}

/** Encode un binaire en base64 sans saturer la pile d'appels. */
function enBase64(tampon: ArrayBuffer): string {
  const octets = new Uint8Array(tampon);
  // btoa attend une chaine : on la construit par tranches, car passer
  // des centaines de milliers d'octets d'un coup a String.fromCharCode
  // depasse la limite d'arguments et leve une RangeError.
  const TRANCHE = 0x8000;
  let texte = "";
  for (let i = 0; i < octets.length; i += TRANCHE) {
    texte += String.fromCharCode(...octets.subarray(i, i + TRANCHE));
  }
  return btoa(texte);
}

export async function preparer(fichier: File): Promise<Charge> {
  if (estClasseur(fichier.name)) {
    return {
      filename: fichier.name,
      file_base64: enBase64(await fichier.arrayBuffer()),
    };
  }
  return { filename: fichier.name, csv_text: await fichier.text() };
}

export type Feuille = {
  nom: string;
  lignes: number;
  colonnes: string[];
  vide: boolean;
};
