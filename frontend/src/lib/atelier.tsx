/**
 * L'espace de travail courant et le fichier sélectionné.
 *
 * Les deux sont conservés dans le navigateur : passer d'une étape à l'autre ne doit
 * pas faire perdre le contexte, et un rechargement encore moins.
 */
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ErreurApi, api } from "./api";
import type { Fichier, Workspace } from "./types";

const CLE_ESPACE = "meglabs.espace";
const CLE_FICHIER = "meglabs.fichier";

interface Atelier {
  espace: Workspace | null;
  fichiers: Fichier[];
  fichier: Fichier | null;
  chargement: boolean;
  erreur: string | null;
  ouvrirEspace: (nom: string) => Promise<Workspace | null>;
  choisirEspace: (espace: Workspace) => Promise<void>;
  choisirFichier: (fichier: Fichier) => void;
  rafraichir: () => Promise<void>;
  signaler: (message: string | null) => void;
}

const Contexte = createContext<Atelier | null>(null);

export function FournisseurAtelier({ children }: { children: React.ReactNode }) {
  const [espace, setEspace] = useState<Workspace | null>(null);
  const [fichiers, setFichiers] = useState<Fichier[]>([]);
  const [fichier, setFichier] = useState<Fichier | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  const chargerFichiers = useCallback(async (identifiant: string) => {
    const liste = await api.listerFichiers(identifiant);
    setFichiers(liste);
    return liste;
  }, []);

  // Restaure le contexte au démarrage. Un espace supprimé côté serveur ne doit pas
  // bloquer l'application : on repart d'un état vierge.
  useEffect(() => {
    const restaurer = async () => {
      const idEspace = localStorage.getItem(CLE_ESPACE);
      if (!idEspace) {
        setChargement(false);
        return;
      }
      try {
        const trouve = await api.recupererWorkspace(idEspace);
        setEspace(trouve);
        const liste = await chargerFichiers(trouve.id);
        const idFichier = localStorage.getItem(CLE_FICHIER);
        setFichier(liste.find((f) => f.id === idFichier) ?? liste[0] ?? null);
      } catch {
        localStorage.removeItem(CLE_ESPACE);
        localStorage.removeItem(CLE_FICHIER);
      } finally {
        setChargement(false);
      }
    };
    void restaurer();
  }, [chargerFichiers]);

  const choisirEspace = useCallback(
    async (choisi: Workspace) => {
      setEspace(choisi);
      localStorage.setItem(CLE_ESPACE, choisi.id);
      const liste = await chargerFichiers(choisi.id);
      setFichier(liste[0] ?? null);
    },
    [chargerFichiers],
  );

  const ouvrirEspace = useCallback(
    async (nom: string) => {
      try {
        const cree = await api.creerWorkspace(nom);
        await choisirEspace(cree);
        return cree;
      } catch (probleme) {
        setErreur(probleme instanceof ErreurApi ? probleme.message : "Une erreur est survenue.");
        return null;
      }
    },
    [choisirEspace],
  );

  const choisirFichier = useCallback((choisi: Fichier) => {
    setFichier(choisi);
    localStorage.setItem(CLE_FICHIER, choisi.id);
  }, []);

  const rafraichir = useCallback(async () => {
    if (!espace) return;
    const liste = await chargerFichiers(espace.id);
    setFichier((actuel) => liste.find((f) => f.id === actuel?.id) ?? liste[0] ?? null);
  }, [espace, chargerFichiers]);

  const valeur = useMemo<Atelier>(
    () => ({
      espace,
      fichiers,
      fichier,
      chargement,
      erreur,
      ouvrirEspace,
      choisirEspace,
      choisirFichier,
      rafraichir,
      signaler: setErreur,
    }),
    [espace, fichiers, fichier, chargement, erreur, ouvrirEspace, choisirEspace, choisirFichier, rafraichir],
  );

  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useAtelier(): Atelier {
  const contexte = useContext(Contexte);
  if (!contexte) throw new Error("useAtelier doit être utilisé sous FournisseurAtelier.");
  return contexte;
}
