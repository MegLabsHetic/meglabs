"use client";

import { useState } from "react";
import type { Feuille } from "@/lib/fichier";

/**
 * Choix de la feuille a importer dans un classeur.
 *
 * Prendre silencieusement la premiere ferait disparaitre les autres sans que
 * l'utilisateur le sache — d'ou ce dialogue des qu'il y a plus d'une feuille
 * exploitable.
 */
export default function SheetPicker({
  fichier,
  feuilles,
  onChoisir,
  onAnnuler,
}: {
  fichier: string;
  feuilles: Feuille[];
  onChoisir: (nom: string) => void;
  onAnnuler: () => void;
}) {
  const utiles = feuilles.filter((f) => !f.vide);
  const [choisie, setChoisie] = useState(utiles[0]?.nom || feuilles[0]?.nom || "");

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-lg w-full p-6 max-h-[85vh] overflow-y-auto">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined text-2xl text-primary">tab_group</span>
          <div className="min-w-0">
            <h3 className="font-bold">Quelle feuille importer ?</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
              {fichier} · {feuilles.length} feuille{feuilles.length > 1 ? "s" : ""}
            </p>
          </div>
        </div>

        <div className="mt-5 space-y-2">
          {feuilles.map((f) => (
            <label
              key={f.nom}
              className={`flex gap-3 p-3 rounded-lg border transition-colors ${
                f.vide
                  ? "border-slate-200 dark:border-slate-800 opacity-50 cursor-not-allowed"
                  : choisie === f.nom
                    ? "border-primary bg-primary/5 cursor-pointer"
                    : "border-slate-200 dark:border-slate-700 cursor-pointer"
              }`}
            >
              <input
                type="radio"
                name="feuille"
                disabled={f.vide}
                checked={choisie === f.nom}
                onChange={() => setChoisie(f.nom)}
                className="mt-0.5 text-primary focus:ring-primary/30"
              />
              <span className="min-w-0">
                <span className="text-sm font-semibold block truncate">{f.nom}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {f.vide
                    ? "Feuille vide"
                    : `${f.lignes.toLocaleString("fr-FR")} ligne${f.lignes > 1 ? "s" : ""} · ` +
                      `${f.colonnes.length} colonne${f.colonnes.length > 1 ? "s" : ""}`}
                </span>
                {!f.vide && f.colonnes.length > 0 && (
                  <span className="block text-[11px] text-slate-400 truncate mt-0.5">
                    {f.colonnes.slice(0, 6).join(" · ")}
                    {f.colonnes.length > 6 && " …"}
                  </span>
                )}
              </span>
            </label>
          ))}
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400 mt-4">
          Vous pourrez importer les autres feuilles ensuite : chacune devient une table
          de l&apos;entrepôt.
        </p>

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onAnnuler} className="px-4 py-2 text-sm font-semibold text-slate-500">
            Annuler
          </button>
          <button
            onClick={() => onChoisir(choisie)}
            disabled={!choisie}
            className="bg-primary text-white rounded-lg px-5 py-2 text-sm font-bold hover:brightness-110 disabled:opacity-50"
          >
            Importer cette feuille
          </button>
        </div>
      </div>
    </div>
  );
}
