"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Alerte } from "@/components/Alerte";
import { ListeFichiers } from "@/components/ListeFichiers";
import { SelecteurEspace } from "@/components/SelecteurEspace";
import { Sources } from "@/components/Sources";
import { ZoneDepot } from "@/components/ZoneDepot";
import { ErreurApi, api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";
import type { Source } from "@/lib/types";

export default function Donnees() {
  const atelier = useAtelier();
  const router = useRouter();
  const [analyse, setAnalyse] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);

  // Les sources sont relues avec les fichiers : une synchronisation cree des
  // fichiers ET met a jour la source, et afficher l'un sans l'autre laisserait
  // l'ecran a moitie a jour.
  const rafraichirTout = useCallback(async () => {
    if (!atelier.espace) return;
    const [, listees] = await Promise.all([
      atelier.rafraichir(),
      api.sources(atelier.espace.id).catch(() => [] as Source[]),
    ]);
    setSources(listees);
  }, [atelier]);

  useEffect(() => {
    if (!atelier.espace) return;
    let vivant = true;
    api
      .sources(atelier.espace.id)
      .then((listees) => vivant && setSources(listees))
      .catch(() => undefined);
    return () => {
      vivant = false;
    };
  }, [atelier.espace]);

  const deposer = async (fichier: File) => {
    if (!atelier.espace) return;
    setAnalyse(true);
    atelier.signaler(null);
    try {
      const depot = await api.deposer(atelier.espace.id, fichier);
      await atelier.rafraichir();
      atelier.choisirFichier(depot.fichier);
      router.push("/exploration");
    } catch (probleme) {
      atelier.signaler(
        probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.",
      );
    } finally {
      setAnalyse(false);
    }
  };

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="titre-serre text-3xl font-semibold">Données</h1>
      <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
        Déposez vos fichiers. On vous dit ce qu&apos;ils contiennent, ce qui cloche, et ce
        qu&apos;il faut protéger — avant qu&apos;une seule ligne ne parte ailleurs.
      </p>

      <div className="cascade mt-6 space-y-6">
        <SelecteurEspace />

        {atelier.erreur && <Alerte message={atelier.erreur} />}

        {atelier.espace ? (
          <>
            <ZoneDepot enCours={analyse} onFichier={deposer} />
            <Sources
              espaceId={atelier.espace.id}
              sources={sources}
              onChange={rafraichirTout}
              onErreur={atelier.signaler}
            />
            <ListeFichiers
              fichiers={atelier.fichiers}
              selection={atelier.fichier}
              onChoisir={(choisi) => {
                atelier.choisirFichier(choisi);
                router.push("/exploration");
              }}
            />
          </>
        ) : (
          <p className="text-sm" style={{ color: "var(--ink-2)" }}>
            Ouvrez d&apos;abord un espace de travail pour y déposer des fichiers.
          </p>
        )}
      </div>
    </main>
  );
}
