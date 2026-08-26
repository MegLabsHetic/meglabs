/**
 * L'état des données d'un espace, agrégé depuis ce que le backend calcule déjà.
 *
 * Aucun endpoint nouveau : le profil de chaque fichier contient les dimensions,
 * le score de qualité et son explication, les anomalies par colonne et les
 * doublons. Le tableau de bord ne mesure rien lui-même, il rassemble.
 *
 * Cette distinction compte : tout ce qui s'affiche ici est mesuré. Rien n'est
 * estimé, rien n'est illustratif.
 */

import type { Detection, Fichier, Profil } from "@/lib/types";

export interface FichierAnalyse {
  fichier: Fichier;
  profil: Profil;
  pii: Detection[];
}

export interface Sante {
  nbFichiers: number;
  nbLignes: number;
  nbColonnes: number;
  /** Moyenne pondérée par le nombre de lignes : un fichier de 10 lignes ne pèse
   *  pas autant qu'un de 10 000 dans la santé d'un espace. */
  scoreMoyen: number | null;
  doublons: number;
  parFichier: { nom: string; score: number; lignes: number; colonnes: number }[];
  penalites: { critere: string; impact: number }[];
  anomalies: { libelle: string; colonnes: number }[];
  pii: { type: string; colonnes: number }[];
  incompletes: { fichier: string; colonne: string; part: number }[];
}

const ANOMALIES: Record<string, string> = {
  formats_multiples: "Formats de date mélangés",
  valeurs_extremes: "Valeurs extrêmes",
  modalites_variantes: "Modalités variantes",
};

/** Au-delà, la liste cesse d'être un signal et devient un inventaire. */
const MAX_INCOMPLETES = 5;

/** En dessous, une colonne incomplète n'est pas un problème à signaler. */
const SEUIL_INCOMPLETE = 0.05;

function cumuler<T>(entrees: T[], cle: (entree: T) => string): Map<string, number> {
  const total = new Map<string, number>();
  for (const entree of entrees) {
    const nom = cle(entree);
    total.set(nom, (total.get(nom) ?? 0) + 1);
  }
  return total;
}

function trierParPoids(total: Map<string, number>): { nom: string; nombre: number }[] {
  return [...total.entries()]
    .map(([nom, nombre]) => ({ nom, nombre }))
    .sort((a, b) => b.nombre - a.nombre);
}

export function agreger(analyses: FichierAnalyse[]): Sante {
  const nbLignes = analyses.reduce((total, a) => total + a.profil.nb_lignes, 0);
  const nbColonnes = analyses.reduce((total, a) => total + a.profil.nb_colonnes, 0);

  const pondere = analyses.reduce((total, a) => total + a.profil.score_qualite * a.profil.nb_lignes, 0);
  const scoreMoyen = nbLignes > 0 ? Math.round((pondere / nbLignes) * 10) / 10 : null;

  // Les pénalités portent le même libellé d'un fichier à l'autre : les additionner
  // dit ce qui coûte le plus de qualité à l'échelle de l'espace.
  const parCritere = new Map<string, number>();
  for (const analyse of analyses) {
    for (const penalite of analyse.profil.explication_qualite) {
      parCritere.set(penalite.critere, (parCritere.get(penalite.critere) ?? 0) + penalite.impact);
    }
  }

  const toutesColonnes = analyses.flatMap((analyse) =>
    analyse.profil.colonnes.map((colonne) => ({ colonne, fichier: analyse.fichier.nom })),
  );

  const anomalies = cumuler(
    toutesColonnes.flatMap(({ colonne }) => colonne.anomalies),
    (anomalie) => ANOMALIES[anomalie.type] ?? anomalie.type,
  );

  const pii = cumuler(
    analyses.flatMap((analyse) => analyse.pii),
    (detection) => detection.type_pii,
  );

  return {
    nbFichiers: analyses.length,
    nbLignes,
    nbColonnes,
    scoreMoyen,
    doublons: analyses.reduce((total, a) => total + a.profil.doublons.nombre, 0),

    parFichier: analyses.map((analyse) => ({
      nom: analyse.fichier.nom,
      score: analyse.profil.score_qualite,
      lignes: analyse.profil.nb_lignes,
      colonnes: analyse.profil.nb_colonnes,
    })),

    penalites: [...parCritere.entries()]
      .map(([critere, impact]) => ({ critere, impact: Math.round(impact * 10) / 10 }))
      // Le plus pénalisant d'abord : c'est là qu'un nettoyage rapporte le plus.
      .sort((a, b) => a.impact - b.impact),

    anomalies: trierParPoids(anomalies).map(({ nom, nombre }) => ({
      libelle: nom,
      colonnes: nombre,
    })),

    pii: trierParPoids(pii).map(({ nom, nombre }) => ({ type: nom, colonnes: nombre })),

    incompletes: toutesColonnes
      .filter(({ colonne }) => colonne.part_manquantes >= SEUIL_INCOMPLETE)
      .sort((a, b) => b.colonne.part_manquantes - a.colonne.part_manquantes)
      .slice(0, MAX_INCOMPLETES)
      .map(({ colonne, fichier }) => ({
        fichier,
        colonne: colonne.nom,
        part: colonne.part_manquantes,
      })),
  };
}

/** Le vert n'est jamais seul : le chiffre l'accompagne partout où cette couleur sert. */
export function couleurScore(score: number): string {
  if (score >= 90) return "var(--etat-bon)";
  if (score >= 75) return "var(--etat-attention)";
  if (score >= 50) return "var(--etat-serieux)";
  return "var(--etat-faible)";
}
