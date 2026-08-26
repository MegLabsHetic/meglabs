/**
 * Brancher une base, choisir ses tables, les faire entrer.
 *
 * Trois écrans en un, parce que c'est une seule intention : « je veux mes
 * données ici ». Les séparer en pages obligerait à naviguer entre trois endroits
 * pour une action qui se pense d'un bloc.
 *
 * Le mot de passe n'est jamais réaffiché. Il part une fois, il est chiffré au
 * repos, et ce qui revient porte des puces à sa place — de sorte que personne
 * ne puisse le relire depuis l'interface, pas même la personne qui l'a saisi.
 */
"use client";

import { useState } from "react";

import { Carte } from "@/components/Carte";
import { ErreurApi, api } from "@/lib/api";
import type { Source, TableDistante } from "@/lib/types";

const NOMBRE = new Intl.NumberFormat("fr-FR");

/** Au-delà, on ne copie plus une base, on la déménage. La borne est côté serveur ; ceci l'annonce. */
const MAX_TABLES = 20;

type Etape = "liste" | "connexion" | "tables";

function Champ({
  libelle,
  valeur,
  onChange,
  type = "text",
  aide,
  requis = true,
}: {
  libelle: string;
  valeur: string;
  onChange: (valeur: string) => void;
  type?: string;
  aide?: string;
  requis?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs" style={{ color: "var(--ink-2)" }}>
        {libelle}
        {!requis && <span style={{ color: "var(--ink-muted)" }}> · facultatif</span>}
      </span>
      <input
        type={type}
        value={valeur}
        required={requis}
        onChange={(evenement) => onChange(evenement.target.value)}
        className="rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
        style={{
          borderColor: "var(--filet)",
          background: "var(--fond)",
          color: "var(--ink-1)",
        }}
      />
      {aide && (
        <span className="text-xs" style={{ color: "var(--ink-muted)" }}>
          {aide}
        </span>
      )}
    </label>
  );
}

export function Sources({
  espaceId,
  sources,
  onChange,
  onErreur,
}: {
  espaceId: string;
  sources: Source[];
  onChange: () => Promise<void> | void;
  onErreur: (message: string | null) => void;
}) {
  const [etape, setEtape] = useState<Etape>("liste");
  const [occupe, setOccupe] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  const [tables, setTables] = useState<TableDistante[]>([]);
  const [choisies, setChoisies] = useState<Set<string>>(new Set());
  const [formulaire, setFormulaire] = useState({
    nom: "",
    hote: "",
    port: "5432",
    base: "",
    utilisateur: "",
    mot_de_passe: "",
    schema_cible: "public",
  });

  const echouer = (probleme: unknown) =>
    onErreur(probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.");

  const connecter = async () => {
    setOccupe(true);
    onErreur(null);
    try {
      const creee = await api.connecterSource(espaceId, {
        ...formulaire,
        port: Number(formulaire.port) || 5432,
      });
      setSource(creee);
      setTables(await api.tablesSource(creee.id));
      setChoisies(new Set());
      setEtape("tables");
      await onChange();
    } catch (probleme) {
      echouer(probleme);
    } finally {
      setOccupe(false);
    }
  };

  const ouvrir = async (choisie: Source) => {
    setOccupe(true);
    onErreur(null);
    try {
      setSource(choisie);
      setTables(await api.tablesSource(choisie.id));
      setChoisies(new Set());
      setEtape("tables");
    } catch (probleme) {
      echouer(probleme);
    } finally {
      setOccupe(false);
    }
  };

  const synchroniser = async () => {
    if (!source) return;
    setOccupe(true);
    onErreur(null);
    try {
      await api.synchroniserSource(source.id, [...choisies]);
      setEtape("liste");
      await onChange();
    } catch (probleme) {
      echouer(probleme);
    } finally {
      setOccupe(false);
    }
  };

  // --- Choix des tables ------------------------------------------------------

  if (etape === "tables") {
    const trop = choisies.size > MAX_TABLES;
    return (
      <Carte className="flex flex-col gap-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-medium">
            {source?.nom} — {tables.length} table{tables.length > 1 ? "s" : ""}
          </h2>
          <button
            type="button"
            onClick={() => setEtape("liste")}
            className="text-xs underline underline-offset-4"
            style={{ color: "var(--ink-muted)" }}
          >
            Retour
          </button>
        </div>

        {tables.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
            Aucune table lisible dans ce schéma. Le compte a-t-il le droit de le consulter ?
          </p>
        ) : (
          <div className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
            {tables.map((table) => {
              const active = choisies.has(table.nom);
              return (
                <label
                  key={`${table.schema}.${table.nom}`}
                  className="flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition-colors"
                  style={{
                    borderColor: active ? "var(--accent-piste)" : "var(--filet)",
                    background: active ? "var(--voile)" : "transparent",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={active}
                    disabled={occupe}
                    onChange={() => {
                      const suivant = new Set(choisies);
                      if (suivant.has(table.nom)) suivant.delete(table.nom);
                      else suivant.add(table.nom);
                      setChoisies(suivant);
                    }}
                    className="size-4 shrink-0 accent-[var(--accent)]"
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">{table.nom}</span>
                  {/* Estimée, pas comptée : un COUNT(*) par table prendrait des
                      minutes sur une grosse base pour un chiffre qui sert à choisir. */}
                  <span
                    className="chiffres-alignes shrink-0 text-xs"
                    style={{ color: "var(--ink-muted)" }}
                  >
                    {table.lignes === null ? "—" : `~${NOMBRE.format(table.lignes)} lignes`}
                  </span>
                </label>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs" style={{ color: trop ? "var(--etat-attention)" : "var(--ink-muted)" }}>
            {choisies.size === 0
              ? "Sélectionnez les tables à faire entrer."
              : trop
                ? `${choisies.size} tables sélectionnées — ${MAX_TABLES} au maximum par synchronisation.`
                : `${choisies.size} table${choisies.size > 1 ? "s" : ""} · elles seront profilées et analysées comme des fichiers déposés.`}
          </p>
          <button
            type="button"
            disabled={occupe || choisies.size === 0 || trop}
            onClick={synchroniser}
            className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
            style={{ background: "var(--accent)", color: "#04110f" }}
          >
            {occupe ? "Copie en cours…" : "Faire entrer"}
          </button>
        </div>
      </Carte>
    );
  }

  // --- Formulaire de connexion -----------------------------------------------

  if (etape === "connexion") {
    return (
      <Carte>
        <form
          className="flex flex-col gap-4"
          onSubmit={(evenement) => {
            evenement.preventDefault();
            void connecter();
          }}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-medium">Connecter une base PostgreSQL</h2>
            <button
              type="button"
              onClick={() => setEtape("liste")}
              className="text-xs underline underline-offset-4"
              style={{ color: "var(--ink-muted)" }}
            >
              Annuler
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Champ
              libelle="Adresse du serveur"
              valeur={formulaire.hote}
              onChange={(hote) => setFormulaire({ ...formulaire, hote })}
              aide="Doit être joignable depuis Internet."
            />
            <Champ
              libelle="Port"
              type="number"
              valeur={formulaire.port}
              onChange={(port) => setFormulaire({ ...formulaire, port })}
            />
            <Champ
              libelle="Base"
              valeur={formulaire.base}
              onChange={(base) => setFormulaire({ ...formulaire, base })}
            />
            <Champ
              libelle="Schéma"
              valeur={formulaire.schema_cible}
              onChange={(schema_cible) => setFormulaire({ ...formulaire, schema_cible })}
            />
            <Champ
              libelle="Utilisateur"
              valeur={formulaire.utilisateur}
              onChange={(utilisateur) => setFormulaire({ ...formulaire, utilisateur })}
              aide="Un compte en lecture seule suffit."
            />
            <Champ
              libelle="Mot de passe"
              type="password"
              valeur={formulaire.mot_de_passe}
              onChange={(mot_de_passe) => setFormulaire({ ...formulaire, mot_de_passe })}
              aide="Chiffré au repos, jamais réaffiché."
              requis={false}
            />
            <Champ
              libelle="Nom de la source"
              valeur={formulaire.nom}
              onChange={(nom) => setFormulaire({ ...formulaire, nom })}
              requis={false}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
              La connexion est testée avant d&apos;être enregistrée. Rien n&apos;est écrit
              dans votre base : la session est ouverte en lecture seule.
            </p>
            <button
              type="submit"
              disabled={occupe}
              className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
              style={{ background: "var(--accent)", color: "#04110f" }}
            >
              {occupe ? "Connexion…" : "Tester et connecter"}
            </button>
          </div>
        </form>
      </Carte>
    );
  }

  // --- Liste des sources -----------------------------------------------------

  return (
    <Carte className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium">Sources connectées</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--ink-muted)" }}>
            Une table copiée depuis une base traverse exactement le même chemin qu&apos;un
            fichier déposé : profilage, détection de données personnelles, questions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEtape("connexion")}
          className="shrink-0 rounded-lg border px-3 py-1.5 text-xs transition-colors"
          style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
        >
          Connecter une base
        </button>
      </div>

      {sources.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
          Aucune source. Vous pouvez déposer un fichier ci-dessus, ou brancher une base.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {sources.map((connectee) => (
            <li key={connectee.id}>
              <button
                type="button"
                disabled={occupe}
                onClick={() => ouvrir(connectee)}
                className="flex w-full items-baseline justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-colors disabled:opacity-50"
                style={{ borderColor: "var(--filet)" }}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm">{connectee.nom}</span>
                  <span className="text-xs" style={{ color: "var(--ink-muted)" }}>
                    {connectee.config.utilisateur}@{connectee.config.hote} ·{" "}
                    {connectee.tables_synchronisees > 0
                      ? `${connectee.tables_synchronisees} table${connectee.tables_synchronisees > 1 ? "s" : ""} importée${connectee.tables_synchronisees > 1 ? "s" : ""}`
                      : "jamais synchronisée"}
                  </span>
                </span>
                <span className="shrink-0 text-xs" style={{ color: "var(--accent)" }}>
                  Choisir des tables
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Carte>
  );
}
