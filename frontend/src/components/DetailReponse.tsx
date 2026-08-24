/**
 * Ce qui se cache derrière une réponse : la requête, le tableau, l'auto-réparation
 * et le coût.
 *
 * Tout est replié par défaut. La promesse de transparence n'est pas d'imposer du SQL
 * à quelqu'un qui n'en veut pas — c'est qu'il soit toujours là pour qui le demande.
 */
"use client";

import { useState } from "react";

import type { AppelTrace, EvenementReparation, EvenementSql } from "@/lib/sse";

function Pliable({
  titre,
  accent,
  children,
}: {
  titre: string;
  accent?: string;
  children: React.ReactNode;
}) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOuvert(!ouvert)}
        className="flex items-center gap-1.5 text-xs transition-colors"
        style={{ color: accent ?? "var(--ink-3)" }}
      >
        <span aria-hidden className="inline-block w-2.5">
          {ouvert ? "−" : "+"}
        </span>
        {titre}
      </button>
      {ouvert && <div className="mt-2">{children}</div>}
    </div>
  );
}

/**
 * La requête, repliée sur elle-même plutôt que coupée à droite : une ligne tronquée
 * ne se lit pas, et personne ne pense à faire défiler un bloc de code.
 */
function Requete({ sql }: { sql: string }) {
  return (
    <pre
      className="whitespace-pre-wrap wrap-break-word rounded-lg border p-3 text-xs leading-relaxed"
      style={{
        borderColor: "var(--filet)",
        background: "var(--fond)",
        color: "var(--ink-2)",
      }}
    >
      <code>{sql}</code>
    </pre>
  );
}

function Tableau({
  colonnes,
  lignes,
  tronque,
}: {
  colonnes: string[];
  lignes: (string | number | null)[][];
  tronque: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr style={{ color: "var(--ink-muted)" }}>
            {colonnes.map((colonne) => (
              <th key={colonne} className="border-b px-2 py-1.5 text-left font-normal"
                  style={{ borderColor: "var(--filet)" }}>
                {colonne}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((ligne, rang) => (
            <tr key={rang}>
              {ligne.map((valeur, colonne) => (
                <td
                  key={colonne}
                  className="border-b px-2 py-1.5 chiffres-alignes"
                  style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
                >
                  {valeur === null ? "—" : String(valeur)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {tronque && (
        <p className="mt-2 text-xs" style={{ color: "var(--ink-muted)" }}>
          Affichage limité : la requête a renvoyé davantage de lignes.
        </p>
      )}
    </div>
  );
}

function Reparation({ reparation }: { reparation: EvenementReparation }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs" style={{ color: "var(--ink-2)" }}>
        {reparation.explication}
      </p>
      <pre
        className="overflow-x-auto rounded-lg border p-2.5 text-xs line-through"
        style={{
          borderColor: "color-mix(in oklab, var(--etat-faible) 35%, var(--filet))",
          background: "var(--fond)",
          color: "var(--ink-muted)",
        }}
      >
        <code>{reparation.sql_echoue}</code>
      </pre>
      <pre
        className="overflow-x-auto rounded-lg border p-2.5 text-xs"
        style={{
          borderColor: "color-mix(in oklab, var(--etat-bon) 35%, var(--filet))",
          background: "var(--fond)",
          color: "var(--ink-2)",
        }}
      >
        <code>{reparation.sql_corrige}</code>
      </pre>
    </div>
  );
}

function Depense({ trace }: { trace: AppelTrace[] }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr style={{ color: "var(--ink-muted)" }}>
          {["Agent", "Modèle", "Entrée", "Sortie", "Durée", "Coût"].map((entete) => (
            <th key={entete} className="px-2 py-1 text-left font-normal">
              {entete}
            </th>
          ))}
        </tr>
      </thead>
      <tbody style={{ color: "var(--ink-2)" }}>
        {trace.map((appel, rang) => (
          <tr key={rang}>
            <td className="px-2 py-1">{appel.agent}</td>
            <td className="px-2 py-1">{appel.modele}</td>
            <td className="px-2 py-1 chiffres-alignes">{appel.tokens_entree}</td>
            <td className="px-2 py-1 chiffres-alignes">{appel.tokens_sortie}</td>
            <td className="px-2 py-1 chiffres-alignes">{appel.duree_ms} ms</td>
            <td className="px-2 py-1 chiffres-alignes">{appel.cout_centimes.toFixed(4)} ¢</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DetailReponse({
  sql,
  colonnes,
  lignes,
  tronque,
  reparation,
  trace,
}: {
  sql: EvenementSql | null;
  colonnes: string[];
  lignes: (string | number | null)[][];
  tronque: boolean;
  reparation: EvenementReparation | null;
  trace: AppelTrace[];
}) {
  const rien = !sql && !reparation && trace.length === 0;
  if (rien) return null;

  return (
    <div className="mt-3 flex flex-col gap-2 border-t pt-3" style={{ borderColor: "var(--filet)" }}>
      {reparation && (
        <Pliable titre="La requête a été corrigée automatiquement" accent="var(--etat-attention)">
          <Reparation reparation={reparation} />
        </Pliable>
      )}
      {sql && (
        <Pliable titre={`Requête exécutée · ${sql.duree_ms} ms · ${sql.nb_lignes} ligne(s)`}>
          <Requete sql={sql.sql} />
        </Pliable>
      )}
      {colonnes.length > 0 && (
        <Pliable titre="Résultat détaillé">
          <Tableau colonnes={colonnes} lignes={lignes} tronque={tronque} />
        </Pliable>
      )}
      {trace.length > 0 && (
        <Pliable titre={`${trace.length} appel(s) au modèle`}>
          <Depense trace={trace} />
        </Pliable>
      )}
    </div>
  );
}
