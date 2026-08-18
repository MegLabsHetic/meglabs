/** Choisir un espace de travail existant, ou en ouvrir un nouveau. */
"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";
import type { Workspace } from "@/lib/types";

export function SelecteurEspace() {
  const { espace, ouvrirEspace, choisirEspace } = useAtelier();
  const [existants, setExistants] = useState<Workspace[]>([]);
  const [nom, setNom] = useState("");
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    void api
      .listerWorkspaces()
      .then(setExistants)
      .catch(() => setExistants([]));
  }, [espace]);

  const creer = async () => {
    const propre = nom.trim();
    if (!propre) return;
    setEnCours(true);
    await ouvrirEspace(propre);
    setNom("");
    setEnCours(false);
  };

  const autres = existants.filter((candidat) => candidat.id !== espace?.id);

  return (
    <div
      className="verre p-4"
    >
      <h2 className="text-sm font-medium">Espace de travail</h2>
      <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
        Un espace regroupe les fichiers d&apos;une même analyse. Les questions posées plus
        tard porteront sur l&apos;ensemble de ses fichiers.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <input
          value={nom}
          onChange={(evenement) => setNom(evenement.target.value)}
          onKeyDown={(evenement) => evenement.key === "Enter" && creer()}
          placeholder="Nom du nouvel espace, par exemple « Analyse RH »"
          className="min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm outline-none"
          style={{
            borderColor: "var(--filet)",
            background: "var(--fond)",
            color: "var(--ink-1)",
          }}
        />
        <button
          type="button"
          onClick={creer}
          disabled={enCours || !nom.trim()}
          className="rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
          style={{
            background: "linear-gradient(135deg, var(--deco-a), var(--accent))",
            color: "#04070f",
            boxShadow: "var(--lueur)",
          }}
        >
          Ouvrir
        </button>
      </div>

      {autres.length > 0 && (
        <div className="mt-3">
          <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
            Reprendre un espace existant
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {autres.slice(0, 8).map((candidat) => (
              <button
                key={candidat.id}
                type="button"
                onClick={() => void choisirEspace(candidat)}
                className="max-w-[220px] truncate rounded-lg border px-2.5 py-1 text-xs transition-colors"
                style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
              >
                {candidat.nom}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
