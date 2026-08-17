import { EtapeAVenir } from "@/components/EtapeAVenir";

export default function TableauDeBord() {
  return (
    <EtapeAVenir
      titre="Tableau de bord"
      resume="Les indicateurs qui comptent, et ce qu'ils veulent dire."
      attendu="sprint 3"
      contenu={[
        "Des indicateurs clés calculés depuis les fichiers de l'espace",
        "Deux à trois graphiques, chacun accompagné de son interprétation en français",
        "Des insights proactifs : la plateforme pose les questions avant vous",
        "Des packs métier qui proposent les bonnes questions selon vos colonnes",
      ]}
    />
  );
}
