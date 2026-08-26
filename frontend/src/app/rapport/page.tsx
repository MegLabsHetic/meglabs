/**
 * Le rapport de l'espace : un document transmissible tel quel.
 *
 * Tout ce qui s'y trouve a été mesuré ailleurs dans la plateforme — les fichiers
 * et leurs défauts par le profilage, les corrections par le nettoyage, les
 * questions par la conversation. Cette page n'ajoute aucun chiffre, elle les
 * rassemble dans l'ordre où on veut les lire.
 *
 * Le score de confiance est affiché AVEC ses composantes. Un chiffre seul se
 * subit ; avec ce qui le compose, il se discute — et chaque composante se
 * vérifie plus bas dans le document.
 */
"use client";

import { useEffect, useState } from "react";

import { Alerte } from "@/components/Alerte";
import { Carte } from "@/components/Carte";
import { ErreurApi, api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";
import { couleurScore } from "@/lib/sante";
import type { Rapport as RapportDonnees } from "@/lib/types";

const NOMBRE = new Intl.NumberFormat("fr-FR");

const ANOMALIES: Record<string, string> = {
  formats_multiples: "formats de date mélangés",
  valeurs_extremes: "valeurs extrêmes",
  modalites_variantes: "modalités variantes",
};

const CORRECTIONS: Record<string, string> = {
  supprimer_doublons: "Lignes dupliquées supprimées",
  normaliser_casse: "Casse et espaces uniformisés",
  uniformiser_dates: "Format de date unifié",
  imputer_mediane: "Valeurs absentes remplacées par la médiane",
  imputer_frequent: "Valeurs absentes remplacées par la plus fréquente",
  supprimer_lignes_vides: "Lignes sans valeur supprimées",
};

function Section({
  numero,
  titre,
  children,
}: {
  numero: number;
  titre: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-baseline gap-2.5 text-sm font-medium">
        {/* Numérotées parce que c'est un document qui se cite : « voir la
            section 3 » doit désigner quelque chose. */}
        <span className="chiffres-alignes text-xs" style={{ color: "var(--ink-muted)" }}>
          {String(numero).padStart(2, "0")}
        </span>
        {titre}
      </h2>
      {children}
    </section>
  );
}

function Vide({ message }: { message: string }) {
  return (
    <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
      {message}
    </p>
  );
}

export default function Rapport() {
  const { espace, chargement } = useAtelier();
  const [rapport, setRapport] = useState<RapportDonnees | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (!espace) return;
    let vivant = true;
    api
      .rapport(espace.id)
      .then((recu) => vivant && setRapport(recu))
      .catch((probleme: unknown) => {
        if (!vivant) return;
        setErreur(
          probleme instanceof ErreurApi ? probleme.message : "Le rapport n'a pas pu être lu.",
        );
      });
    return () => {
      vivant = false;
    };
  }, [espace]);

  if (chargement) return null;

  if (!espace) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="titre-serre text-3xl">Rapport</h1>
        <p className="mt-3" style={{ color: "var(--ink-2)" }}>
          Aucun espace ouvert.{" "}
          <a href="/donnees" className="underline underline-offset-4">
            Déposez un fichier
          </a>{" "}
          pour commencer.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="titre-serre text-3xl">Rapport</h1>
          <p className="mt-1.5 text-sm" style={{ color: "var(--ink-2)" }}>
            {rapport?.espace ?? espace.nom} — tout ce qui suit est mesuré, rien n&apos;est estimé.
          </p>
        </div>
        {rapport && (
          <div className="flex shrink-0 gap-2">
            <a
              href={api.lienNotebook(espace.id)}
              className="rounded-lg border px-3 py-1.5 text-xs transition-colors"
              style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
            >
              Exporter en notebook
            </a>
            <button
              type="button"
              onClick={() => window.print()}
              className="rounded-lg border px-3 py-1.5 text-xs transition-colors"
              style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
            >
              Imprimer
            </button>
          </div>
        )}
      </header>

      {erreur && <Alerte message={erreur} />}
      {!rapport && !erreur && <Vide message="Assemblage du rapport…" />}

      {rapport && (
        <>
          <Carte className="flex flex-col gap-4">
            <div className="flex items-baseline gap-3">
              <span
                className="chiffres-alignes text-4xl leading-none"
                style={{ color: couleurScore(rapport.confiance.score) }}
              >
                {rapport.confiance.score}
              </span>
              <span className="text-sm" style={{ color: "var(--ink-2)" }}>
                sur 100 — confiance dans cette analyse
              </span>
            </div>

            <div className="flex flex-col gap-2">
              {rapport.confiance.composantes.map((composante) => (
                <div
                  key={composante.libelle}
                  className="flex items-baseline justify-between gap-3 text-xs"
                >
                  <span style={{ color: "var(--ink-2)" }}>
                    {composante.libelle}
                    <span style={{ color: "var(--ink-muted)" }}>
                      {" "}
                      · pèse {Math.round(composante.poids * 100)} %
                    </span>
                  </span>
                  <span className="chiffres-alignes" style={{ color: "var(--ink-1)" }}>
                    {composante.valeur}
                  </span>
                </div>
              ))}
            </div>
          </Carte>

          <Section numero={1} titre="Sources analysées">
            {rapport.sources.length === 0 ? (
              <Vide message="Aucun fichier dans cet espace." />
            ) : (
              <div className="flex flex-col gap-3">
                {rapport.sources.map((source) => (
                  <Carte key={source.nom} className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm">{source.nom}</span>
                      {source.score_qualite !== null && (
                        <span
                          className="chiffres-alignes text-xs"
                          style={{ color: couleurScore(source.score_qualite) }}
                        >
                          qualité {source.score_qualite} / 100
                        </span>
                      )}
                    </div>
                    <p className="chiffres-alignes text-xs" style={{ color: "var(--ink-muted)" }}>
                      {NOMBRE.format(source.lignes)} lignes · {source.colonnes} colonnes
                      {source.doublons > 0 && ` · ${source.doublons} doublons`}
                      {source.statut_pii === "masquee" && " · données personnelles masquées"}
                      {source.statut_pii === "detectee" && " · données personnelles détectées"}
                    </p>
                    {source.anomalies.length > 0 && (
                      <ul className="flex flex-col gap-1">
                        {source.anomalies.map((anomalie) => (
                          <li
                            key={anomalie.type}
                            className="text-xs"
                            style={{ color: "var(--etat-attention)" }}
                          >
                            {ANOMALIES[anomalie.type] ?? anomalie.type} —{" "}
                            {anomalie.colonnes.join(", ")}
                          </li>
                        ))}
                      </ul>
                    )}
                  </Carte>
                ))}
              </div>
            )}
          </Section>

          <Section numero={2} titre="Corrections appliquées">
            {rapport.corrections.length === 0 ? (
              <Vide message="Aucune correction n'a été appliquée. Les données sont analysées telles qu'elles ont été déposées." />
            ) : (
              <ul className="flex flex-col gap-2">
                {rapport.corrections.map((correction, rang) => (
                  <li
                    key={`${correction.fichier}-${correction.type}-${rang}`}
                    className="flex items-baseline justify-between gap-3 text-xs"
                  >
                    <span style={{ color: "var(--ink-2)" }}>
                      {CORRECTIONS[correction.type] ?? correction.type}
                      {correction.colonne && ` · ${correction.colonne}`}
                      <span style={{ color: "var(--ink-muted)" }}> · {correction.fichier}</span>
                    </span>
                    <span className="chiffres-alignes" style={{ color: "var(--ink-muted)" }}>
                      {correction.lignes_affectees} lignes
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section numero={3} titre="Questions posées">
            {rapport.questions.length === 0 ? (
              <Vide message="Aucune question n'a encore été posée sur cet espace." />
            ) : (
              <div className="flex flex-col gap-4">
                {rapport.questions.map((echange, rang) => (
                  <div key={rang} className="flex flex-col gap-1.5">
                    <p className="text-sm font-medium">{echange.question}</p>
                    <p className="text-xs leading-relaxed" style={{ color: "var(--ink-2)" }}>
                      {echange.reponse}
                    </p>
                    {echange.sql && (
                      <pre
                        className="overflow-x-auto rounded-lg border p-2 text-xs"
                        style={{
                          borderColor: "var(--filet)",
                          background: "var(--fond)",
                          color: "var(--ink-muted)",
                        }}
                      >
                        <code>{echange.sql}</code>
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section numero={4} titre="Ce que l'analyse a coûté">
            <p className="chiffres-alignes text-xs" style={{ color: "var(--ink-2)" }}>
              {rapport.cout.centimes.toFixed(3)} centime
              {rapport.cout.centimes > 1 ? "s" : ""} pour {rapport.cout.questions} question
              {rapport.cout.questions > 1 ? "s" : ""}.
            </p>
            <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
              Le profilage, la détection de données personnelles et le nettoyage ne coûtent
              rien : ils sont calculés, pas demandés à un modèle. Seules la traduction des
              questions et la rédaction des réponses appellent un fournisseur.
            </p>
          </Section>
        </>
      )}
    </div>
  );
}
