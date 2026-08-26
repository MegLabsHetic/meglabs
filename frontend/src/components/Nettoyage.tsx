/**
 * Les corrections proposées, avec leur impact — et la case pour les refuser.
 *
 * C'est le point où la plateforme cesse d'être une boîte noire. Chaque ligne dit
 * ce qui sera fait, pourquoi, et combien de lignes changeront. Rien ne s'applique
 * sans un clic, et rien n'est irréversible : le fichier d'origine n'est jamais
 * réécrit, l'état courant est le rejeu des actions actives.
 *
 * Les propositions sont calculées à partir du profil, pas demandées à un modèle.
 * Un modèle n'aura jamais compté les doublons, il les aura estimés — et le chiffre
 * affiché ici sert à décider, donc il doit être juste.
 */
"use client";

import { useState } from "react";

export interface Proposition {
  type: string;
  libelle: string;
  raison: string;
  colonne: string | null;
  lignes_affectees: number;
}

export function Nettoyage({
  propositions,
  enCours,
  onAppliquer,
}: {
  propositions: Proposition[];
  enCours: boolean;
  onAppliquer: (types: string[]) => void;
}) {
  // Tout est coché d'avance : ce sont des corrections que les défauts détectés
  // justifient. Décocher est un choix, cocher ne devrait pas être un travail.
  const [choisies, setChoisies] = useState<Set<string>>(
    () => new Set(propositions.map((proposition) => proposition.type)),
  );

  if (propositions.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--ink-muted)" }}>
        Aucune correction à proposer sur ce fichier — les défauts détectés ne justifient
        pas d&apos;intervention.
      </p>
    );
  }

  const basculer = (type: string) => {
    const suivant = new Set(choisies);
    if (suivant.has(type)) suivant.delete(type);
    else suivant.add(type);
    setChoisies(suivant);
  };

  const total = propositions
    .filter((proposition) => choisies.has(proposition.type))
    .reduce((somme, proposition) => somme + proposition.lignes_affectees, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2.5">
        {propositions.map((proposition) => {
          const active = choisies.has(proposition.type);
          return (
            <label
              key={proposition.type}
              className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors"
              style={{
                borderColor: active ? "var(--accent-piste)" : "var(--filet)",
                background: active ? "var(--voile)" : "transparent",
              }}
            >
              <input
                type="checkbox"
                checked={active}
                disabled={enCours}
                onChange={() => basculer(proposition.type)}
                className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
              />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="flex flex-wrap items-baseline gap-x-2 text-sm">
                  <span>{proposition.libelle}</span>
                  <span
                    className="chiffres-alignes text-xs"
                    style={{ color: active ? "var(--accent-clair)" : "var(--ink-muted)" }}
                  >
                    {proposition.lignes_affectees} ligne
                    {proposition.lignes_affectees > 1 ? "s" : ""}
                  </span>
                </span>
                {/* Le motif, pas seulement l'action : quelqu'un qui ne comprend
                    pas pourquoi ne peut pas décider s'il refuse. */}
                <span className="text-xs" style={{ color: "var(--ink-2)" }}>
                  {proposition.raison}
                </span>
              </span>
            </label>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
          {choisies.size === 0
            ? "Aucune correction sélectionnée."
            : `${choisies.size} correction${choisies.size > 1 ? "s" : ""} · ${total} ligne${
                total > 1 ? "s" : ""
              } touchée${total > 1 ? "s" : ""}. Le fichier d'origine reste intact.`}
        </p>
        <button
          type="button"
          disabled={enCours || choisies.size === 0}
          onClick={() => onAppliquer([...choisies])}
          className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
          style={{ background: "var(--accent)", color: "#04110f" }}
        >
          {enCours ? "Application…" : "Appliquer"}
        </button>
      </div>
    </div>
  );
}
