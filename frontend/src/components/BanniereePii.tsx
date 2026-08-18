/**
 * Bannière des données personnelles.
 *
 * C'est l'écran qui rend visible la promesse de souveraineté. Il dit ce qui a été
 * trouvé, ce qui partira au modèle si on ne fait rien, et propose l'action.
 */
"use client";

import type { Detection, StatutPii } from "@/lib/types";

export function BanniereePii({
  statut,
  detections,
  colonnesMasquees,
  valeursRemplacees,
  enCours,
  onPseudonymiser,
}: {
  statut: StatutPii;
  detections: Detection[];
  colonnesMasquees: string[];
  valeursRemplacees: number;
  enCours: boolean;
  onPseudonymiser: () => void;
}) {
  if (statut === "aucune") {
    return (
      <div
        className="flex items-start gap-3 panneau-doux p-4"
      >
        <span aria-hidden className="pt-0.5" style={{ color: "var(--etat-bon)" }}>
          ●
        </span>
        <p className="text-sm">
          <span className="font-medium">Aucune donnée personnelle détectée.</span>{" "}
          <span style={{ color: "var(--ink-2)" }}>
            Ce fichier ne contient ni adresse, ni téléphone, ni identifiant de personne.
          </span>
        </p>
      </div>
    );
  }

  if (statut === "masquee") {
    return (
      <div
        className="panneau-doux p-4"
      >
        <div className="flex items-start gap-3">
          <span aria-hidden className="pt-0.5" style={{ color: "var(--etat-bon)" }}>
            ●
          </span>
          <div className="text-sm">
            <p className="font-medium">
              {colonnesMasquees.length} colonne
              {colonnesMasquees.length > 1 ? "s" : ""} pseudonymisée
              {colonnesMasquees.length > 1 ? "s" : ""} —{" "}
              <span className="chiffres-alignes">{valeursRemplacees}</span> valeurs
              remplacées.
            </p>
            <p className="mt-1" style={{ color: "var(--ink-2)" }}>
              Les valeurs d&apos;origine ont été retirées du fichier. Seule une empreinte
              est conservée, ce qui garantit qu&apos;une même valeur donnera toujours le
              même jeton — mais rend le retour en arrière impossible.
            </p>
            <p className="mt-2 flex flex-wrap gap-1.5">
              {colonnesMasquees.map((colonne) => (
                <span
                  key={colonne}
                  className="rounded-md border px-2 py-0.5 text-xs"
                  style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
                >
                  {colonne}
                </span>
              ))}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        background: "color-mix(in oklab, var(--etat-attention) 7%, var(--panneau))",
        borderColor: "color-mix(in oklab, var(--etat-attention) 35%, var(--filet))",
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span aria-hidden className="pt-0.5" style={{ color: "var(--etat-attention)" }}>
            ▲
          </span>
          <div className="text-sm">
            <p className="font-medium">
              {detections.length} colonne{detections.length > 1 ? "s" : ""} contien
              {detections.length > 1 ? "nent" : "t"} des données personnelles.
            </p>
            <p className="mt-1" style={{ color: "var(--ink-2)" }}>
              Elles resteront sur ce serveur. Les pseudonymiser garantit qu&apos;aucune
              valeur réelle n&apos;atteindra jamais le modèle de langage.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onPseudonymiser}
          disabled={enCours}
          className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-60"
          style={{
            background: "linear-gradient(135deg, var(--deco-a), var(--accent))",
            color: "#04070f",
            boxShadow: "var(--lueur)",
          }}
        >
          {enCours ? "Pseudonymisation…" : "Pseudonymiser"}
        </button>
      </div>

      <ul className="mt-3 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {detections.map((detection) => (
          <li
            key={detection.colonne}
            className="flex items-baseline justify-between gap-3 rounded-lg border px-2.5 py-1.5 text-xs"
            style={{ borderColor: "var(--filet)", background: "var(--panneau)" }}
          >
            <span className="truncate font-medium">{detection.colonne}</span>
            <span className="shrink-0" style={{ color: "var(--ink-2)" }}>
              {detection.type_pii}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
