/**
 * L'état de santé des données de l'espace.
 *
 * Tout ce qui s'affiche ici est mesuré : le backend calcule déjà les dimensions,
 * les scores, les anomalies et les colonnes personnelles de chaque fichier. Cette
 * page rassemble, elle n'estime rien.
 *
 * L'ordre suit ce qu'on veut savoir : combien, puis dans quel état, puis ce qui
 * pèse sur cet état, puis ce qu'il faut protéger.
 */
"use client";

import { useEffect, useState } from "react";

import { Alerte } from "@/components/Alerte";
import { Carte } from "@/components/Carte";
import { TuileStat } from "@/components/TuileStat";
import { api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";
import { agreger, couleurScore, type FichierAnalyse, type Sante } from "@/lib/sante";

const NOMBRE = new Intl.NumberFormat("fr-FR");
const PART = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 1 });

/** Une barre nue : le tableau de bord compare des grandeurs, il ne raconte pas
 *  d'histoire — pas besoin d'axes ni de grille. */
function Barre({ part, couleur }: { part: number; couleur: string }) {
  return (
    <span className="block h-1.5 w-full rounded-sm" style={{ background: "var(--voile)" }}>
      <span
        className="block h-full rounded-sm"
        style={{ width: `${Math.max(part * 100, 1.5)}%`, background: couleur }}
      />
    </span>
  );
}

function Section({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <Carte className="flex flex-col gap-4">
      <h2 className="text-sm font-medium">{titre}</h2>
      {children}
    </Carte>
  );
}

function Vide({ message }: { message: string }) {
  return (
    <p className="text-xs" style={{ color: "var(--ink-muted)" }}>
      {message}
    </p>
  );
}

export default function TableauDeBord() {
  const { espace, fichiers, chargement } = useAtelier();
  const [sante, setSante] = useState<Sante | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    // Pas de remise à zéro ici : le rendu s'arrête plus haut quand l'espace est
    // vide, donc un état résiduel n'est jamais lu — et écrire dans l'état depuis
    // le corps d'un effet déclenche un rendu en cascade.
    if (fichiers.length === 0) return;
    let vivant = true;

    // Les profils sont demandés en parallèle : les enchaîner rendrait l'attente
    // proportionnelle au nombre de fichiers pour aucun gain.
    Promise.all(
      fichiers.map(async (fichier): Promise<FichierAnalyse> => {
        const [profil, pii] = await Promise.all([
          api.profil(fichier.id),
          api.donneesPersonnelles(fichier.id),
        ]);
        return { fichier, profil, pii };
      }),
    )
      .then((analyses) => vivant && setSante(agreger(analyses)))
      .catch(() => vivant && setErreur("Les profils n'ont pas pu être relus. Rechargez la page."));

    return () => {
      vivant = false;
    };
  }, [fichiers]);

  if (chargement) return null;

  if (!espace || fichiers.length === 0) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-16">
        <h1 className="titre-serre text-3xl">Tableau de bord</h1>
        <p className="mt-3" style={{ color: "var(--ink-2)" }}>
          Aucun fichier dans cet espace.{" "}
          <a href="/donnees" className="underline underline-offset-4">
            Déposez-en un
          </a>{" "}
          pour voir l&apos;état de vos données.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="titre-serre text-3xl">Tableau de bord</h1>
        <p className="mt-1.5 text-sm" style={{ color: "var(--ink-2)" }}>
          L&apos;état de vos données, mesuré sur les fichiers de cet espace.
        </p>
      </header>

      {erreur && <Alerte message={erreur} />}
      {!sante && !erreur && <Vide message="Lecture des profils…" />}

      {sante && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <TuileStat libelle="Fichiers" valeur={String(sante.nbFichiers)} nombre={sante.nbFichiers} />
            <TuileStat
              libelle="Lignes"
              valeur={NOMBRE.format(sante.nbLignes)}
              nombre={sante.nbLignes}
            />
            <TuileStat
              libelle="Colonnes"
              valeur={String(sante.nbColonnes)}
              nombre={sante.nbColonnes}
            />
            <TuileStat
              libelle="Qualité moyenne"
              valeur={sante.scoreMoyen === null ? "—" : `${sante.scoreMoyen} / 100`}
              nombre={sante.scoreMoyen ?? undefined}
              decimales={1}
              precision="pondérée par le nombre de lignes"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section titre="Qualité par fichier">
              <div className="flex flex-col gap-3">
                {sante.parFichier.map((fichier) => (
                  <div key={fichier.nom} className="flex flex-col gap-1.5">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-xs" style={{ color: "var(--ink-2)" }}>
                        {fichier.nom}
                      </span>
                      <span
                        className="chiffres-alignes shrink-0 text-xs"
                        style={{ color: couleurScore(fichier.score) }}
                      >
                        {fichier.score} / 100
                      </span>
                    </div>
                    <Barre part={fichier.score / 100} couleur={couleurScore(fichier.score)} />
                    <span className="text-xs" style={{ color: "var(--ink-muted)" }}>
                      {NOMBRE.format(fichier.lignes)} lignes · {fichier.colonnes} colonnes
                    </span>
                  </div>
                ))}
              </div>
            </Section>

            <Section titre="Ce qui pèse sur la qualité">
              {sante.penalites.length === 0 ? (
                <Vide message="Aucune pénalité relevée sur cet espace." />
              ) : (
                <div className="flex flex-col gap-3">
                  {sante.penalites.map((penalite) => (
                    <div key={penalite.critere} className="flex flex-col gap-1.5">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-xs" style={{ color: "var(--ink-2)" }}>
                          {penalite.critere}
                        </span>
                        <span
                          className="chiffres-alignes shrink-0 text-xs"
                          style={{ color: "var(--etat-serieux)" }}
                        >
                          {penalite.impact} pts
                        </span>
                      </div>
                      <Barre
                        part={
                          Math.abs(penalite.impact) /
                          Math.max(...sante.penalites.map((p) => Math.abs(p.impact)))
                        }
                        couleur="var(--etat-serieux)"
                      />
                    </div>
                  ))}
                </div>
              )}
            </Section>

            <Section titre="Anomalies détectées">
              {sante.anomalies.length === 0 ? (
                <Vide message="Aucune anomalie détectée." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {sante.anomalies.map((anomalie) => (
                    <li
                      key={anomalie.libelle}
                      className="flex items-baseline justify-between gap-3 text-xs"
                    >
                      <span style={{ color: "var(--ink-2)" }}>{anomalie.libelle}</span>
                      <span className="chiffres-alignes" style={{ color: "var(--ink-muted)" }}>
                        {anomalie.colonnes} colonne{anomalie.colonnes > 1 ? "s" : ""}
                      </span>
                    </li>
                  ))}
                  {sante.doublons > 0 && (
                    <li className="flex items-baseline justify-between gap-3 text-xs">
                      <span style={{ color: "var(--ink-2)" }}>Lignes dupliquées</span>
                      <span className="chiffres-alignes" style={{ color: "var(--ink-muted)" }}>
                        {NOMBRE.format(sante.doublons)}
                      </span>
                    </li>
                  )}
                </ul>
              )}
            </Section>

            <Section titre="Données personnelles">
              {sante.pii.length === 0 ? (
                <Vide message="Aucune donnée personnelle détectée sur cet espace." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {sante.pii.map((detection) => (
                    <li
                      key={detection.type}
                      className="flex items-baseline justify-between gap-3 text-xs"
                    >
                      <span style={{ color: "var(--ink-2)" }}>{detection.type}</span>
                      <span className="chiffres-alignes" style={{ color: "var(--ink-muted)" }}>
                        {detection.colonnes} colonne{detection.colonnes > 1 ? "s" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </div>

          {sante.incompletes.length > 0 && (
            <Section titre="Colonnes les plus incomplètes">
              <div className="flex flex-col gap-3">
                {sante.incompletes.map((colonne) => (
                  <div key={`${colonne.fichier}-${colonne.colonne}`} className="flex flex-col gap-1.5">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-xs" style={{ color: "var(--ink-2)" }}>
                        {colonne.colonne}
                        <span style={{ color: "var(--ink-muted)" }}> · {colonne.fichier}</span>
                      </span>
                      <span
                        className="chiffres-alignes shrink-0 text-xs"
                        style={{ color: "var(--etat-attention)" }}
                      >
                        {PART.format(colonne.part)} absentes
                      </span>
                    </div>
                    <Barre part={colonne.part} couleur="var(--etat-attention)" />
                  </div>
                ))}
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  );
}
