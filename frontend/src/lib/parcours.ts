/** Les cinq étapes du parcours. L'ordre est celui du travail réel, pas d'un menu. */

export interface Etape {
  chemin: string;
  titre: string;
  resume: string;
  /** Sprint qui livre l'étape. Sert à dire honnêtement ce qui n'existe pas encore. */
  disponible: boolean;
  attendu?: string;
}

export const ETAPES: Etape[] = [
  {
    chemin: "/donnees",
    titre: "Données",
    resume: "Déposer des fichiers et protéger ce qui est personnel",
    disponible: true,
  },
  {
    chemin: "/exploration",
    titre: "Exploration",
    resume: "Comprendre ce que contiennent les données",
    disponible: true,
  },
  {
    chemin: "/dashboard",
    titre: "Tableau de bord",
    resume: "Indicateurs et graphiques interprétés",
    disponible: false,
    attendu: "sprint 3",
  },
  {
    chemin: "/ia",
    titre: "IA & prédictions",
    resume: "Poser ses questions en français, simuler",
    disponible: false,
    attendu: "sprints 2 et 3",
  },
  {
    chemin: "/rapport",
    titre: "Rapport",
    resume: "Un document transmissible en dix sections",
    disponible: false,
    attendu: "sprint 4",
  },
];
