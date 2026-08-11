/** Contrats renvoyés par l'API. Les noms de champs sont en français, comme côté backend. */

export type StatutPii = "aucune" | "detectee" | "masquee";

export interface Anomalie {
  type: "formats_multiples" | "valeurs_extremes" | "modalites_variantes";
  detail: string;
}

export interface Modalite {
  valeur: string;
  occurrences: number;
}

export interface StatistiquesColonne {
  minimum?: number;
  maximum?: number;
  moyenne?: number;
  mediane?: number;
  ecart_type?: number;
  modalites_frequentes?: Modalite[];
}

export interface Colonne {
  nom: string;
  type: string;
  valeurs_manquantes: number;
  part_manquantes: number;
  cardinalite: number;
  exemples: string[];
  statistiques: StatistiquesColonne;
  anomalies: Anomalie[];
}

export interface Penalite {
  critere: string;
  impact: number;
  detail: string;
}

export interface Profil {
  nb_lignes: number;
  nb_colonnes: number;
  score_qualite: number;
  doublons: { nombre: number; part: number };
  explication_qualite: Penalite[];
  colonnes: Colonne[];
}

export interface Fichier {
  id: string;
  nom: string;
  format: string;
  taille_octets: number;
  statut_pii: StatutPii;
  score_qualite: number | null;
  cree_le: string;
}

export interface Detection {
  colonne: string;
  type_pii: string;
  confiance: number;
  exemple_masque: string;
}

export interface Depot {
  fichier: Fichier;
  profil: Profil;
  donnees_personnelles: Detection[];
}

export interface Pseudonymisation {
  fichier: Fichier;
  colonnes_pseudonymisees: string[];
  valeurs_remplacees: number;
  profil: Profil;
}

export interface Workspace {
  id: string;
  nom: string;
  cree_le: string;
}
