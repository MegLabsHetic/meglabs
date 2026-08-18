"use client";

import { useRef, useState } from "react";

/** Dépôt par glisser-déposer, avec le clic en repli — tout le monde ne glisse pas. */
export function ZoneDepot({
  enCours,
  onFichier,
}: {
  enCours: boolean;
  onFichier: (fichier: File) => void;
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

      <button
        type="button"
        onClick={() => champ.current?.click()}
        disabled={enCours}
        className="mt-4 rounded-lg border px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-60"
        style={{ borderColor: "var(--filet)" }}
      >
        Choisir un fichier
      </button>

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
