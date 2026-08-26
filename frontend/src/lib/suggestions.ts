/**
 * Les questions à poser, déduites des données réellement chargées.
 *
 * C'est la réponse à la page blanche : quelqu'un qui découvre la plateforme sait
 * ce qu'il veut savoir, mais pas comment le demander. Des exemples écrits en dur
 * ne l'aident pas — ils parlent d'un fichier qui n'est pas le sien.
 *
 * Rien n'est demandé à un modèle : le profil contient les types, la cardinalité
 * et les anomalies. Choisir quoi proposer est une lecture de ce profil, donc du
 * calcul. Un appel coûterait un jeton pour un résultat moins prévisible.
 */

import type { Colonne, Profil } from "@/lib/types";

/** Au-delà, ce n'est plus une aide mais un menu à lire. */
const MAX_SUGGESTIONS = 4;

/** En dessous de deux modalités il n'y a rien à répartir ; au-delà de douze, la
 *  réponse devient un tableau interminable. */
const MODALITES_MIN = 2;
const MODALITES_MAX = 12;

/**
 * Une colonne aux modalités variantes compte « Data », « data » et « Data » comme
 * trois valeurs : sa cardinalité est gonflée par le défaut, pas par la réalité.
 * L'orchestrateur regroupe sur la valeur normalisée, donc la répartition finale
 * tiendra dans la limite normale. Sans cette tolérance, la colonne la plus
 * intéressante du fichier est justement celle qu'on n'ose plus proposer.
 */
const MODALITES_MAX_SALE = 30;

// Les booléens sont écartés : « répartition par a quitte » se lit mal, et deux
// modalités ne font pas une répartition. Trois bonnes suggestions valent mieux
// que quatre dont une bancale.
const CATEGORIELS = new Set(["catégorie"]);
const NUMERIQUES = new Set(["entier", "décimal"]);

/** `salaire_annuel` se lit mal au milieu d'une phrase. */
function lisible(nom: string): string {
  return nom.replace(/_/g, " ");
}

/** « de ancienneté » n'existe pas en français. */
function de(nom: string): string {
  const mot = lisible(nom);
  return /^[aeiouyàâäéèêëîïôöùûüh]/i.test(mot) ? `d'${mot}` : `de ${mot}`;
}

function variantes(colonne: Colonne): boolean {
  return colonne.anomalies.some((anomalie) => anomalie.type === "modalites_variantes");
}

function estCategorielle(colonne: Colonne): boolean {
  if (!CATEGORIELS.has(colonne.type) || colonne.cardinalite < MODALITES_MIN) return false;
  return colonne.cardinalite <= (variantes(colonne) ? MODALITES_MAX_SALE : MODALITES_MAX);
}

/** Un identifiant est numérique sans être une mesure : en faire une moyenne
 *  produirait une réponse juste et vide de sens. */
function estMesure(colonne: Colonne): boolean {
  return NUMERIQUES.has(colonne.type) && colonne.cardinalite > 1;
}

/**
 * Toutes les formulations évitent l'accord : « répartition », « moyenne » et
 * « évolution » sont féminins quel que soit le nom de la colonne, et « le total »
 * masculin. Une phrase construite avec l'article de la colonne serait fausse une
 * fois sur deux — et une faute de français dans l'interface se remarque plus
 * qu'une suggestion manquante.
 */
export function suggerer(profil: Profil): string[] {
  const categorielles = profil.colonnes
    .filter(estCategorielle)
    // La répartition la plus lisible est celle qui a le moins de modalités.
    .sort((a, b) => a.cardinalite - b.cardinalite);
  const mesures = profil.colonnes.filter(estMesure);
  const dates = profil.colonnes.filter((colonne) => colonne.type === "date");

  const questions: string[] = [];

  if (categorielles.length > 0) {
    questions.push(`Quelle est la répartition par ${lisible(categorielles[0].nom)} ?`);
  }

  // Le croisement d'une mesure et d'une catégorie : la vraie valeur ajoutée par
  // rapport à un tableur. On prend la deuxième catégorie s'il y en a une, pour
  // que les deux suggestions ne parlent pas de la même colonne.
  if (mesures.length > 0 && categorielles.length > 0) {
    const croisee = categorielles[1] ?? categorielles[0];
    questions.push(
      `Quelle est la moyenne ${de(mesures[0].nom)} par ${lisible(croisee.nom)} ?`,
    );
  }

  if (dates.length > 0 && mesures.length > 0) {
    questions.push(`Quelle est l'évolution ${de(mesures[0].nom)} par ${lisible(dates[0].nom)} ?`);
  }

  // Les défauts détectés valent une question : ils sont la raison d'être du
  // profilage, et personne ne pense à les interroger spontanément.
  const extremes = profil.colonnes.find((colonne) =>
    colonne.anomalies.some((anomalie) => anomalie.type === "valeurs_extremes"),
  );
  if (extremes) {
    questions.push(`Quelles sont les valeurs extrêmes ${de(extremes.nom)} ?`);
  }

  if (profil.doublons.nombre > 0) {
    questions.push("Combien de lignes sont dupliquées ?");
  }

  if (mesures.length > 1) {
    questions.push(`Quel est le total ${de(mesures[1].nom)} ?`);
  }

  return questions.slice(0, MAX_SUGGESTIONS);
}
