import { apiFetch } from "@/lib/api";

/**
 * Etapes d'un traitement, et suivi du job qui l'execute.
 *
 * Deux sources alimentent la meme liste : les etapes que le navigateur
 * execute lui-meme (lire le fichier, appeler le diagnostic) et celles que la
 * pipeline publie pendant qu'elle travaille. Elles parlent le meme langage,
 * si bien que l'utilisateur voit une seule progression continue.
 */

export type EtatEtape = "attente" | "cours" | "faite" | "echec";

export type Etape = {
  cle: string;
  libelle: string;
  etat: EtatEtape;
  detail?: string | null;
};

/** Met a jour une etape sans toucher aux autres. */
export function majEtape(
  etapes: Etape[],
  cle: string,
  etat: EtatEtape,
  detail?: string | null
): Etape[] {
  return etapes.map((e) =>
    e.cle === cle ? { ...e, etat, detail: detail !== undefined ? detail : e.detail } : e
  );
}

/** Termine une etape et lance la suivante. */
export function avancer(
  etapes: Etape[],
  cle: string,
  suivante: string,
  detail?: string
): Etape[] {
  return majEtape(majEtape(etapes, cle, "faite", detail), suivante, "cours");
}

export function tailleLisible(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / 1024 / 1024).toFixed(1)} Mo`.replace(".", ",");
}

/** Plan de la phase d'analyse, avant que l'utilisateur ne valide quoi que ce soit. */
export function planAnalyse(nom: string): Etape[] {
  const classeur = /\.xlsx?$/i.test(nom);
  return [
    { cle: "lecture", libelle: "Lecture du fichier", etat: "cours" },
    // Un CSV n'a qu'une table : annoncer une etape « feuilles » qui ne
    // servira pas donnerait une liste qui n'aboutit jamais.
    ...(classeur
      ? [{ cle: "feuilles", libelle: "Reconnaissance des feuilles", etat: "attente" as EtatEtape }]
      : []),
    { cle: "diagnostic", libelle: "Diagnostic de la structure et de la qualité", etat: "attente" },
  ];
}

/**
 * Meme plan, mais la lecture (et le choix de la feuille) sont deja faits.
 * Sert quand l'utilisateur reprend la main apres avoir choisi sa feuille :
 * afficher « Lecture du fichier » comme en cours serait faux.
 */
export function planApresLecture(nom: string, feuille?: string): Etape[] {
  return majEtape(
    majEtape(planAnalyse(nom), "lecture", "faite"),
    "feuilles",
    "faite",
    feuille ? `feuille « ${feuille} »` : undefined
  );
}

/** Plan de la phase de chargement, une fois les corrections validees. */
export function planChargement(): Etape[] {
  return [
    { cle: "envoi", libelle: "Envoi au serveur", etat: "cours" },
    { cle: "priseencharge", libelle: "Prise en charge par le moteur", etat: "attente" },
  ];
}

/**
 * Attend la fin d'un job en relayant son avancement.
 *
 * Les etapes annoncees par la pipeline remplacent l'attente generique des
 * qu'elles arrivent : a partir de la, ce qui s'affiche est ce que le serveur
 * est reellement en train de faire.
 */
export async function suivreJob(
  jobId: string,
  onEtapes: (etapes: Etape[]) => void,
  sondagesMax = 120
): Promise<any> {
  const envoye: Etape[] = [
    { cle: "envoi", libelle: "Envoi au serveur", etat: "faite" },
  ];
  let vues: Etape[] | null = null;

  for (let i = 0; i < sondagesMax; i++) {
    const job = await apiFetch<any>(`/v1/jobs/${jobId}`);
    const distantes: Etape[] | undefined = job.progress?.etapes;

    if (distantes?.length) {
      vues = distantes;
      onEtapes([...envoye, ...distantes]);
    } else if (!vues) {
      onEtapes([
        ...envoye,
        { cle: "priseencharge", libelle: "Prise en charge par le moteur", etat: "cours" },
      ]);
    }

    if (job.status === "done") {
      // Le dernier sondage arrive parfois apres la fin : on cloture les
      // etapes restees en cours plutot que de les laisser tourner.
      if (vues) onEtapes([...envoye, ...vues.map((e) => ({ ...e, etat: "faite" as EtatEtape }))]);
      return job;
    }
    if (job.status === "error") throw new Error(job.error || "échec de l'ingestion");
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("délai dépassé");
}
