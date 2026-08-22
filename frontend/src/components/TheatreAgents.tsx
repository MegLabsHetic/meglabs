/**
 * Le théâtre des agents.
 *
 * C'est la preuve visible de l'architecture : sans lui, « multi-agents » n'est
 * qu'une affirmation sur une slide. Chaque agent s'allume quand il travaille et
 * affiche sa durée quand il a fini.
 */
"use client";

import type { EvenementAgent } from "@/lib/sse";

export interface EtapeAgent {
  agent: string;
  detail: string;
  termine: boolean;
  dureeMs?: number;
}

/** Fusionne un événement dans la liste : un agent ne s'affiche qu'une fois. */
export function integrer(etapes: EtapeAgent[], evenement: EvenementAgent): EtapeAgent[] {
  const rang = etapes.findIndex(
    (etape) => etape.agent === evenement.agent && etape.detail === evenement.detail,
  );
  const misAJour: EtapeAgent = {
    agent: evenement.agent,
    detail: evenement.detail,
    termine: evenement.etat === "done",
    dureeMs: evenement.duree_ms,
  };
  if (rang === -1) return [...etapes, misAJour];
  return etapes.map((etape, index) => (index === rang ? misAJour : etape));
}

export function TheatreAgents({ etapes }: { etapes: EtapeAgent[] }) {
  if (etapes.length === 0) return null;

  return (
    <ol className="flex flex-col gap-1.5">
      {etapes.map((etape) => (
        <li
          key={`${etape.agent}-${etape.detail}`}
          className="flex items-center gap-2.5 text-xs"
          style={{ color: etape.termine ? "var(--ink-3)" : "var(--ink-1)" }}
        >
          <span
            aria-hidden
            className={etape.termine ? "h-1.5 w-1.5 rounded-full" : "pulse h-1.5 w-1.5 rounded-full"}
            style={{ background: etape.termine ? "var(--etat-bon)" : "var(--accent)" }}
          />
          <span className="font-medium">{etape.agent}</span>
          <span style={{ color: "var(--ink-muted)" }}>{etape.detail}</span>
          {etape.dureeMs !== undefined && (
            <span className="chiffres-alignes" style={{ color: "var(--ink-muted)" }}>
              {etape.dureeMs} ms
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
