"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alerte } from "@/components/Alerte";
import { BanniereePii } from "@/components/BanniereePii";
import { Carte } from "@/components/Carte";
import { DetailColonne } from "@/components/DetailColonne";
import { ListeFichiers } from "@/components/ListeFichiers";
import { Nettoyage, type Proposition } from "@/components/Nettoyage";
import { ScoreQualite } from "@/components/ScoreQualite";
import { TableauColonnes } from "@/components/TableauColonnes";
import { SqueletteProfil } from "@/components/Squelette";
import { TuileStat } from "@/components/TuileStat";
import { ErreurApi, api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";
import type { Detection, Profil } from "@/lib/types";

export default function Exploration() {
  const atelier = useAtelier();
  const { fichier } = atelier;

  // Le profil est rangé avec l'identifiant du fichier auquel il appartient. Sans ça,
  // enchaîner deux fichiers rapidement laisse la réponse la plus lente écraser la plus
  // récente, et l'écran affiche le profil du mauvais fichier.
  const [donnees, setDonnees] = useState<{
    fichierId: string;
    profil: Profil;
    detections: Detection[];
    propositions: Proposition[];
  } | null>(null);
  const [nettoyage, setNettoyage] = useState(false);
  const [colonneOuverte, setColonneOuverte] = useState<string | null>(null);
  const [masquage, setMasquage] = useState(false);
  const [derniereAction, setDerniereAction] = useState<{
    colonnes: string[];
    valeurs: number;
  } | null>(null);

  const signaler = atelier.signaler;

  useEffect(() => {
    const identifiant = fichier?.id;
    if (!identifiant) return;

    let abandonne = false;
    Promise.all([
      api.profil(identifiant),
      api.donneesPersonnelles(identifiant),
      api.propositionsNettoyage(identifiant),
    ])
      .then(([profil, detections, propositions]) => {
        if (abandonne) return;
        setDonnees({ fichierId: identifiant, profil, detections, propositions });
        setColonneOuverte(null);
      })
      .catch((probleme: unknown) => {
        if (abandonne) return;
        signaler(
          probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.",
        );
      });

    return () => {
      abandonne = true;
    };
  }, [fichier?.id, signaler]);

  const aJour = donnees !== null && donnees.fichierId === fichier?.id;
  const profil = aJour ? donnees.profil : null;
  const detections = aJour ? donnees.detections : [];

  /**
   * Applique les corrections choisies, puis relit tout.
   *
   * Les propositions sont recalculees apres coup : une fois les doublons
   * supprimes, continuer a proposer de les supprimer serait troublant.
   */
  const nettoyer = async (types: string[]) => {
    if (!fichier) return;
    setNettoyage(true);
    atelier.signaler(null);
    try {
      const resultat = await api.nettoyer(fichier.id, types);
      setDonnees({
        fichierId: fichier.id,
        profil: resultat.profil,
        detections: resultat.donnees_personnelles,
        propositions: await api.propositionsNettoyage(fichier.id),
      });
      setColonneOuverte(null);
      await atelier.rafraichir();
    } catch (probleme) {
      atelier.signaler(
        probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.",
      );
    } finally {
      setNettoyage(false);
    }
  };

  const pseudonymiser = async () => {
    if (!fichier) return;
    setMasquage(true);
    atelier.signaler(null);
    try {
      const resultat = await api.pseudonymiser(fichier.id);
      setDonnees({
        fichierId: fichier.id,
        profil: resultat.profil,
        detections: [],
        propositions: await api.propositionsNettoyage(fichier.id),
      });
      setDerniereAction({
        colonnes: resultat.colonnes_pseudonymisees,
        valeurs: resultat.valeurs_remplacees,
      });
      await atelier.rafraichir();
    } catch (probleme) {
      atelier.signaler(
        probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.",
      );
    } finally {
      setMasquage(false);
    }
  };

  if (!fichier) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Exploration</h1>
        <p className="mt-2" style={{ color: "var(--ink-2)" }}>
          Aucun fichier sélectionné.{" "}
          <Link href="/donnees" className="underline underline-offset-2">
            Déposez-en un
          </Link>{" "}
          pour voir ce qu&apos;il contient.
        </p>
      </main>
    );
  }

  const detail = profil?.colonnes.find((colonne) => colonne.nom === colonneOuverte);

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="titre-serre text-3xl font-semibold tracking-tight">{fichier.nom}</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
            {profil
              ? `${profil.nb_lignes.toLocaleString("fr-FR")} lignes · ${profil.nb_colonnes} colonnes`
              : "Lecture du profil…"}
          </p>
        </div>
        <Link
          href="/donnees"
          className="rounded-lg border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--filet)" }}
        >
          Déposer un autre fichier
        </Link>
      </div>

      <div className="cascade mt-6 space-y-6">
        {atelier.erreur && <Alerte message={atelier.erreur} />}

        {atelier.fichiers.length > 1 && (
          <Carte>
            <ListeFichiers
              fichiers={atelier.fichiers}
              selection={fichier}
              onChoisir={atelier.choisirFichier}
            />
          </Carte>
        )}

        <BanniereePii
          statut={fichier.statut_pii}
          detections={detections}
          colonnesMasquees={derniereAction?.colonnes ?? []}
          valeursRemplacees={derniereAction?.valeurs ?? 0}
          enCours={masquage}
          onPseudonymiser={pseudonymiser}
        />

        {profil && donnees && (
          <Carte className="flex flex-col gap-3">
            <div>
              <h2 className="text-sm font-medium">Corrections proposées</h2>
              <p className="mt-1 text-xs" style={{ color: "var(--ink-muted)" }}>
                Calculées depuis le profil, pas devinées. Chacune dit ce qu&apos;elle change
                et combien de lignes elle touche — vous décidez.
              </p>
            </div>
            <Nettoyage
              propositions={donnees.propositions}
              enCours={nettoyage}
              onAppliquer={nettoyer}
            />
          </Carte>
        )}

        {profil && (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <TuileStat
                libelle="Lignes"
                valeur=""
                nombre={profil.nb_lignes}
                precision={`${profil.nb_colonnes} colonnes`}
              />
              <TuileStat
                libelle="Lignes en double"
                valeur=""
                nombre={profil.doublons.nombre}
                precision={`${(profil.doublons.part * 100).toFixed(1)} % du fichier`}
              />
              <TuileStat
                libelle="Colonnes à corriger"
                valeur=""
                nombre={
                  profil.colonnes.filter(
                    (colonne) => colonne.anomalies.length > 0 || colonne.part_manquantes > 0,
                  ).length
                }
                precision="valeurs absentes ou incohérences"
              />
              <TuileStat
                libelle="Colonnes sensibles"
                valeur=""
                nombre={detections.length}
                precision={
                  fichier.statut_pii === "masquee"
                    ? "pseudonymisées"
                    : detections.length > 0
                      ? "à pseudonymiser"
                      : "rien à protéger"
                }
              />
            </div>

            <Carte>
              <ScoreQualite
                score={profil.score_qualite}
                explication={profil.explication_qualite}
              />
            </Carte>

            {detail && (
              <DetailColonne
                colonne={detail}
                nbLignes={profil.nb_lignes}
                onFermer={() => setColonneOuverte(null)}
              />
            )}

            <Carte>
              <TableauColonnes
                colonnes={profil.colonnes}
                selection={colonneOuverte}
                onSelectionner={(nom) =>
                  setColonneOuverte((actuel) => (actuel === nom ? null : nom))
                }
              />
            </Carte>
          </>
        )}

        {!profil && !atelier.erreur && <SqueletteProfil />}
      </div>
    </main>
  );
}
