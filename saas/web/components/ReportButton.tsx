"use client";

import { useState } from "react";
import { apiDownload, uiLangue } from "@/lib/api";

/**
 * Demande le rapport PDF du projet et le telecharge.
 *
 * La generation prend une trentaine de secondes (les indicateurs sont
 * recalcules puis la synthese redigee) : le bouton doit donc afficher son
 * etat, sinon l'utilisateur clique trois fois.
 */
export default function ReportButton({
  projectId,
  demande = "",
  variante = "primaire",
  onErreur,
}: {
  projectId: string;
  demande?: string;
  variante?: "primaire" | "discret";
  onErreur?: (message: string) => void;
}) {
  const [occupe, setOccupe] = useState(false);

  async function generer() {
    if (occupe) return;
    setOccupe(true);
    try {
      await apiDownload(
        `/v1/projects/${projectId}/report`,
        { demande, langue: uiLangue() },
        "rapport.pdf"
      );
    } catch (e: any) {
      onErreur?.(e.message);
    } finally {
      setOccupe(false);
    }
  }

  const classes =
    variante === "primaire"
      ? "bg-primary text-white hover:brightness-110"
      : "border border-slate-200 dark:border-slate-700 hover:border-primary text-slate-700 dark:text-slate-200";

  return (
    <button
      onClick={generer}
      disabled={occupe}
      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-bold transition disabled:opacity-60 ${classes}`}
    >
      {occupe ? (
        <>
          <span className="spinner" />
          Rédaction du rapport…
        </>
      ) : (
        <>
          <span className="material-symbols-outlined text-lg">picture_as_pdf</span>
          Rapport PDF
        </>
      )}
    </button>
  );
}
