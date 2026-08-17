import { EtapeAVenir } from "@/components/EtapeAVenir";

export default function Rapport() {
  return (
    <EtapeAVenir
      titre="Rapport"
      resume="Un document que vous pouvez transmettre tel quel."
      attendu="sprint 4"
      contenu={[
        "Dix sections rédigées en français, avec un score de confiance expliqué",
        "L'export de la session en notebook Python, exécutable",
        "Un lien de partage en lecture seule, révocable",
        "Une ligne sur l'empreinte de l'analyse, avec sa méthodologie",
      ]}
    />
  );
}
