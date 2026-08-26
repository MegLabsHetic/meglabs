"use client";

import { useRef, useState } from "react";

/** Dépôt par glisser-déposer, avec le clic en repli — tout le monde ne glisse pas. */
export function ZoneDepot({
  enCours,
  onFichier,
  onDemonstration,
}: {
  enCours: boolean;
  onFichier: (fichier: File) => void;
  /** Absent quand il n'y a rien à proposer : le bouton disparaît alors. */
  onDemonstration?: () => void;
}) {
  const [survol, setSurvol] = useState(false);
  const champ = useRef<HTMLInputElement>(null);

  const deposer = (fichiers: FileList | null) => {
    const fichier = fichiers?.[0];
    if (fichier) onFichier(fichier);
  };

  return (
    <div
      onDragOver={(evenement) => {
        evenement.preventDefault();
        setSurvol(true);
      }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(evenement) => {
        evenement.preventDefault();
        setSurvol(false);
        deposer(evenement.dataTransfer.files);
      }}
      className="rounded-2xl border border-dashed p-12 text-center transition-all duration-300"
      style={{
        background: survol
          ? "color-mix(in oklab, var(--accent) 10%, var(--eleve))"
          : "color-mix(in oklab, var(--eleve) 70%, transparent)",
        borderColor: survol ? "var(--accent)" : "var(--filet-fort)",
        boxShadow: survol ? "var(--lueur)" : undefined,
      }}
    >
      <p className="text-base font-medium">
        {enCours ? "Analyse en cours…" : "Déposez votre fichier ici"}
      </p>
      <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
        {enCours
          ? "Profilage et recherche de données personnelles."
          : "CSV ou Excel, jusqu'à 100 Mo. Rien n'est envoyé à un modèle de langage."}
      </p>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={() => champ.current?.click()}
          disabled={enCours}
          className="rounded-lg border px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-60"
          style={{ borderColor: "var(--filet)" }}
        >
          Choisir un fichier
        </button>

        {/* La réponse à la page blanche. Quelqu'un qui découvre la plateforme
            sait ce qu'il veut savoir, mais n'a pas forcément un fichier sous la
            main — et sans fichier, il n'y a rien à voir. */}
        {onDemonstration && (
          <button
            type="button"
            onClick={onDemonstration}
            disabled={enCours}
            className="rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-60"
            style={{ background: "var(--accent)", color: "#04110f" }}
          >
            Essayer avec un jeu de démonstration
          </button>
        )}
      </div>

      {onDemonstration && !enCours && (
        <p className="mt-3 text-xs" style={{ color: "var(--ink-muted)" }}>
          232 collaborateurs et 3 000 transactions, avec des défauts volontaires —
          doublons, dates mélangées, salaires aberrants.
        </p>
      )}

      <input
        ref={champ}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={(evenement) => deposer(evenement.target.files)}
      />
    </div>
  );
}
