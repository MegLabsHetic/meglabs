"use client";

import { useEffect, useRef, useState } from "react";
import type { Etape, EtatEtape } from "@/lib/progression";

/**
 * Suivi vivant d'un traitement.
 *
 * Ce que l'utilisateur voit correspond au travail reellement effectue : les
 * etapes cote navigateur sont marquees par le code qui les execute, celles
 * du serveur remontent de la pipeline elle-meme. Rien n'avance tout seul
 * pour faire patienter — une barre qui progresse sans rien mesurer ment.
 *
 * Le plan complet est affiche d'emblee, en attente : on sait ce qui reste.
 */

const ICONE: Record<EtatEtape, string> = {
  attente: "radio_button_unchecked",
  cours: "",
  faite: "check_circle",
  echec: "error",
};

function Chronometre({ actif }: { actif: boolean }) {
  const [s, setS] = useState(0);
  const depart = useRef(Date.now());
  useEffect(() => {
    if (!actif) return;
    const t = setInterval(() => setS(Math.floor((Date.now() - depart.current) / 1000)), 500);
    return () => clearInterval(t);
  }, [actif]);
  if (s < 3) return null;
  return <span className="tabular-nums text-xs text-slate-400">{s}s</span>;
}

export default function Progression({
  titre,
  sousTitre,
  etapes,
  erreur,
  onFermer,
}: {
  titre: string;
  sousTitre?: string;
  etapes: Etape[];
  erreur?: string;
  onFermer?: () => void;
}) {
  const faites = etapes.filter((e) => e.etat === "faite").length;
  const part = etapes.length ? Math.round((faites / etapes.length) * 100) : 0;
  const enCours = etapes.some((e) => e.etat === "cours");

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/40 dark:bg-black/60 backdrop-blur-[2px] flex items-center justify-center p-6"
      role="status"
      aria-live="polite"
    >
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        {/* Barre d'avancement : une etape faite = un cran, rien d'invente. */}
        <div className="h-1 bg-slate-100 dark:bg-slate-800">
          <div
            className={`h-full bg-primary transition-[width] duration-500 ease-out ${
              erreur ? "bg-red-500" : ""
            }`}
            style={{ width: `${erreur ? 100 : part}%` }}
          />
        </div>

        <div className="p-6">
          <div className="flex items-start gap-3">
            <span
              className={`shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${
                erreur ? "bg-red-500/10 text-red-500" : "bg-primary/10 text-primary"
              }`}
            >
              <span className="material-symbols-outlined text-xl">
                {erreur ? "error" : "database"}
              </span>
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="font-bold truncate">{titre}</h3>
              {sousTitre && (
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{sousTitre}</p>
              )}
            </div>
            <Chronometre actif={enCours && !erreur} />
          </div>

          <ol className="mt-5 space-y-0.5">
            {etapes.map((e, i) => (
              <li key={e.cle} className="flex gap-3">
                {/* Colonne des pastilles, reliees par un trait qui se remplit */}
                <div className="flex flex-col items-center shrink-0">
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                      e.etat === "faite"
                        ? "text-emerald-500"
                        : e.etat === "echec"
                        ? "text-red-500"
                        : e.etat === "cours"
                        ? "text-primary"
                        : "text-slate-300 dark:text-slate-700"
                    }`}
                  >
                    {e.etat === "cours" ? (
                      <span className="pg-pulse w-2.5 h-2.5 rounded-full bg-primary" />
                    ) : (
                      <span
                        className={`material-symbols-outlined text-[19px] ${
                          e.etat === "faite" ? "pg-pop" : ""
                        }`}
                      >
                        {ICONE[e.etat]}
                      </span>
                    )}
                  </span>
                  {i < etapes.length - 1 && (
                    <span
                      className={`w-px flex-1 min-h-[14px] transition-colors duration-500 ${
                        e.etat === "faite"
                          ? "bg-emerald-500/40"
                          : "bg-slate-200 dark:bg-slate-800"
                      }`}
                    />
                  )}
                </div>

                <div className="min-w-0 flex-1 pb-2.5">
                  <p
                    className={`text-sm transition-colors ${
                      e.etat === "cours"
                        ? "font-semibold text-slate-900 dark:text-slate-100"
                        : e.etat === "attente"
                        ? "text-slate-400 dark:text-slate-600"
                        : "text-slate-600 dark:text-slate-300"
                    }`}
                  >
                    {e.libelle}
                    {e.etat === "cours" && <span className="pg-points" aria-hidden="true" />}
                  </p>
                  {e.detail && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 tabular-nums truncate">
                      {e.detail}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>

          {erreur ? (
            <div className="mt-2">
              <p className="text-sm text-red-500 bg-red-500/10 rounded-lg px-3 py-2">{erreur}</p>
              {onFermer && (
                <button
                  onClick={onFermer}
                  className="mt-3 w-full bg-slate-100 dark:bg-slate-800 rounded-lg py-2 text-sm font-semibold"
                >
                  Fermer
                </button>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400 mt-1">
              Vos données restent dans l&apos;entrepôt de ce projet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
