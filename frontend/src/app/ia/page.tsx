import { EtapeAVenir } from "@/components/EtapeAVenir";

export default function IntelligenceArtificielle() {
  return (
    <EtapeAVenir
      titre="IA & prédictions"
      resume="Poser ses questions en français, voir le raisonnement, simuler."
      attendu="sprints 2 et 3"
      contenu={[
        "Un chat en français : la question devient du SQL, exécuté sur vos données",
        "Le SQL est affiché, et la chaîne d'agents s'allume en direct",
        "Le coût de chaque réponse, en centimes, visible en permanence",
        "Un modèle de risque de départ, avec des curseurs pour simuler",
      ]}
    />
  );
}
