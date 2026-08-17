"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alerte } from "@/components/Alerte";
import { ListeFichiers } from "@/components/ListeFichiers";
import { SelecteurEspace } from "@/components/SelecteurEspace";
import { ZoneDepot } from "@/components/ZoneDepot";
import { ErreurApi, api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";

export default function Donnees() {
  const atelier = useAtelier();
  const router = useRouter();
  const [analyse, setAnalyse] = useState(false);

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
      <h1 className="text-2xl font-semibold tracking-tight">Données</h1>
      <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
        Déposez vos fichiers. On vous dit ce qu&apos;ils contiennent, ce qui cloche, et ce
        qu&apos;il faut protéger — avant qu&apos;une seule ligne ne parte ailleurs.
      </p>

      <div className="mt-6 space-y-6">
        <SelecteurEspace />

        {atelier.erreur && <Alerte message={atelier.erreur} />}

        {atelier.espace ? (
          <>
            <ZoneDepot enCours={analyse} onFichier={deposer} />
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
