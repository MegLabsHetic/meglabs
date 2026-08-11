"use client";

import { useState } from "react";

import { BanniereePii } from "@/components/BanniereePii";
import { Carte } from "@/components/Carte";
import { ScoreQualite } from "@/components/ScoreQualite";
import { TableauColonnes } from "@/components/TableauColonnes";
import { TuileStat } from "@/components/TuileStat";
import { ZoneDepot } from "@/components/ZoneDepot";
import { ErreurApi, api } from "@/lib/api";
import type { Depot, Detection } from "@/lib/types";

function taille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(0)} ko`;
  return `${(octets / 1024 / 1024).toFixed(1)} Mo`;
}

export default function Accueil() {
  const [depot, setDepot] = useState<Depot | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [colonnesMasquees, setColonnesMasquees] = useState<string[]>([]);
  const [valeursRemplacees, setValeursRemplacees] = useState(0);
  const [erreur, setErreur] = useState<string | null>(null);
  const [analyse, setAnalyse] = useState(false);
  const [masquage, setMasquage] = useState(false);

  const deposer = async (fichier: File) => {
    setAnalyse(true);
    setErreur(null);
    try {
      const espace = await api.creerWorkspace(`Analyse — ${fichier.name}`);
      const resultat = await api.deposer(espace.id, fichier);
      setDepot(resultat);
      setDetections(resultat.donnees_personnelles);
      setColonnesMasquees([]);
      setValeursRemplacees(0);
    } catch (probleme) {
      setErreur(probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.");
      setDepot(null);
    } finally {
      setAnalyse(false);
    }
  };

  const pseudonymiser = async () => {
    if (!depot) return;
    setMasquage(true);
    setErreur(null);
    try {
      const resultat = await api.pseudonymiser(depot.fichier.id);
      setDepot({ ...depot, fichier: resultat.fichier, profil: resultat.profil });
      setColonnesMasquees(resultat.colonnes_pseudonymisees);
      setValeursRemplacees(resultat.valeurs_remplacees);
    } catch (probleme) {
      setErreur(probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.");
    } finally {
      setMasquage(false);
    }
  };

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">MegLabs</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
          Déposez un fichier. On vous dit ce qu&apos;il contient, ce qui cloche, et ce
          qu&apos;il faut protéger — avant qu&apos;une seule ligne ne parte ailleurs.
        </p>
      </header>

      <ZoneOuResultat
        depot={depot}
        analyse={analyse}
        onFichier={deposer}
        onRecommencer={() => {
          setDepot(null);
          setErreur(null);
        }}
      />

      {erreur && (
        <div
          className="mt-4 flex items-start gap-3 rounded-xl border p-4 text-sm"
          style={{
            background: "color-mix(in oklab, var(--etat-faible) 6%, var(--surface-1))",
            borderColor: "color-mix(in oklab, var(--etat-faible) 35%, var(--bordure))",
          }}
        >
          <span aria-hidden className="pt-0.5" style={{ color: "var(--etat-faible)" }}>
            ■
          </span>
          <p>{erreur}</p>
        </div>
      )}

      {depot && (
        <div className="apparait mt-6 space-y-6">
          <BanniereePii
            statut={depot.fichier.statut_pii}
            detections={detections}
            colonnesMasquees={colonnesMasquees}
            valeursRemplacees={valeursRemplacees}
            enCours={masquage}
            onPseudonymiser={pseudonymiser}
          />

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <TuileStat
              libelle="Lignes"
              valeur={depot.profil.nb_lignes.toLocaleString("fr-FR")}
              precision={taille(depot.fichier.taille_octets)}
            />
            <TuileStat
              libelle="Colonnes"
              valeur={String(depot.profil.nb_colonnes)}
              precision={depot.fichier.format.toUpperCase()}
            />
            <TuileStat
              libelle="Lignes en double"
              valeur={depot.profil.doublons.nombre.toLocaleString("fr-FR")}
              precision={`${(depot.profil.doublons.part * 100).toFixed(1)} % du fichier`}
            />
            <TuileStat
              libelle="Colonnes sensibles"
              valeur={String(detections.length)}
              precision={
                depot.fichier.statut_pii === "masquee"
                  ? "pseudonymisées"
                  : detections.length > 0
                    ? "à pseudonymiser"
                    : "rien à protéger"
              }
            />
          </div>

          <Carte>
            <ScoreQualite
              score={depot.profil.score_qualite}
              explication={depot.profil.explication_qualite}
            />
          </Carte>

          <Carte>
            <TableauColonnes colonnes={depot.profil.colonnes} />
          </Carte>
        </div>
      )}
    </main>
  );
}

function ZoneOuResultat({
  depot,
  analyse,
  onFichier,
  onRecommencer,
}: {
  depot: Depot | null;
  analyse: boolean;
  onFichier: (fichier: File) => void;
  onRecommencer: () => void;
}) {
  if (!depot) {
    return <ZoneDepot enCours={analyse} onFichier={onFichier} />;
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <span className="font-medium">{depot.fichier.nom}</span>
        <span className="ml-2 text-sm" style={{ color: "var(--ink-muted)" }}>
          {taille(depot.fichier.taille_octets)}
        </span>
      </div>
      <button
        type="button"
        onClick={onRecommencer}
        className="rounded-lg border px-3 py-1.5 text-sm transition-opacity"
        style={{ borderColor: "var(--bordure)" }}
      >
        Déposer un autre fichier
      </button>
    </div>
  );
}

