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
    resume: "L'état de vos données, mesuré",
    disponible: true,
  },
  {
    chemin: "/ia",
    titre: "IA & prédictions",
    resume: "Poser ses questions en français",
    disponible: true,
  },
  {
    chemin: "/rapport",
    titre: "Rapport",
    resume: "Un document transmissible, chiffres à l'appui",
    disponible: true,
  },
];
