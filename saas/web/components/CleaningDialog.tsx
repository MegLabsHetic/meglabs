"use client";

import { useState } from "react";

/**
 * Etape de structuration : ce qui cloche dans le fichier, avant chargement.
 *
 * Le diagnostic est deterministe cote serveur — aucun appel a un modele,
 * donc ni attente ni quota. Rien n'est applique sans validation : chaque
 * correction dit son impact chiffre, et l'utilisateur decide.
 */

export type ActionNettoyage = {
  type: string;
  column: string | null;
  params: Record<string, unknown>;
  description: string;
  raison: string;
  gravite: "bloquant" | "important" | "mineur";
  recommande: boolean;
  impact?: string;
};

export type Decoupage = {
  cle: string;
  attributs: string[];
  lignes: number;
  economie: number;
  nom_suggere: string;
};

export type Diagnostic = {
  lignes: number;
  colonnes: number;
  doublons: number;
  actions: ActionNettoyage[];
  decoupages: Decoupage[];
  constats: string[];
  apercu: Record<string, unknown>[];
};

const GRAVITE = {
  bloquant: {
    libelle: "Empêche l'analyse",
    couleur: "text-red-500",
    fond: "bg-red-500/10 border-red-500/25",
    icone: "block",
  },
  important: {
    libelle: "Fausse les résultats",
    couleur: "text-amber-600 dark:text-amber-500",
    fond: "bg-amber-500/10 border-amber-500/25",
    icone: "warning",
  },
  mineur: {
    libelle: "Confort",
    couleur: "text-slate-500",
    fond: "bg-slate-500/10 border-slate-500/20",
    icone: "info",
  },
} as const;

export default function CleaningDialog({
  fichier,
  diagnostic,
  onValider,
  onAnnuler,
}: {
  fichier: string;
  diagnostic: Diagnostic;
  onValider: (actions: ActionNettoyage[], decoupages: Decoupage[]) => void;
  onAnnuler: () => void;
}) {
  // Les corrections recommandees sont cochees par defaut : le cas courant
  // doit se regler en un clic, sans lire toute la liste.
  const [retenues, setRetenues] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(diagnostic.actions.map((a, i) => [i, a.recommande]))
  );
  const [voirApercu, setVoirApercu] = useState(false);
  // Le decoupage restructure les donnees : il n'est pas coche par defaut,
  // c'est une decision de modelisation, pas une correction evidente.
  const [tables, setTables] = useState<Record<number, boolean>>({});

  const choisies = diagnostic.actions.filter((_, i) => retenues[i]);
  const decoupagesChoisis = (diagnostic.decoupages || []).filter((_, i) => tables[i]);
  const colonnesApercu = Object.keys(diagnostic.apercu?.[0] || {});

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[88vh] flex flex-col">
        {/* En-tete */}
        <div className="p-6 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-2xl text-primary">
              cleaning_services
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="font-bold">Structuration des données</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
                {fichier} · {diagnostic.lignes.toLocaleString("fr-FR")} lignes ·{" "}
                {diagnostic.colonnes} colonnes
              </p>
            </div>
          </div>

          {diagnostic.actions.length === 0 ? (
            <p className="mt-4 flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-500">
              <span className="material-symbols-outlined text-lg">check_circle</span>
              Aucun problème détecté — le fichier est exploitable tel quel.
            </p>
          ) : (
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
              {diagnostic.actions.length} point{diagnostic.actions.length > 1 ? "s" : ""} à
              corriger avant de charger. Décochez ce que vous voulez conserver.
            </p>
          )}
        </div>

        {/* Corrections proposees */}
        <div className="flex-1 overflow-y-auto p-6 space-y-2.5">
          {diagnostic.actions.map((a, i) => {
            const g = GRAVITE[a.gravite] || GRAVITE.mineur;
            return (
              <label
                key={i}
                className={`flex gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                  retenues[i]
                    ? "border-primary/40 bg-primary/5"
                    : "border-slate-200 dark:border-slate-800"
                }`}
              >
                <input
                  type="checkbox"
                  checked={!!retenues[i]}
                  onChange={(e) => setRetenues({ ...retenues, [i]: e.target.checked })}
                  className="mt-0.5 rounded text-primary focus:ring-primary/30"
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold" dir="auto">
                      {a.description}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold border ${g.fond} ${g.couleur}`}
                    >
                      <span className="material-symbols-outlined text-[11px]">{g.icone}</span>
                      {g.libelle}
                    </span>
                  </span>
                  <span className="block text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {a.raison}
                  </span>
                  {a.impact && (
                    <span className="block text-[11px] text-slate-400 mt-1 tabular-nums">
                      → {a.impact}
                    </span>
                  )}
                </span>
              </label>
            );
          })}

          {(diagnostic.decoupages || []).length > 0 && (
            <div className="pt-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Découper en tables liées
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2.5">
                Ces informations se répètent à chaque ligne. Les sortir dans leur propre
                table évite de les recopier, et corriger une valeur la corrige partout.
              </p>
              <div className="space-y-2">
                {diagnostic.decoupages.map((d, i) => (
                  <label
                    key={i}
                    className={`flex gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                      tables[i]
                        ? "border-primary/40 bg-primary/5"
                        : "border-slate-200 dark:border-slate-800"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={!!tables[i]}
                      onChange={(e) => setTables({ ...tables, [i]: e.target.checked })}
                      className="mt-0.5 rounded text-primary focus:ring-primary/30"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="text-sm font-semibold flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-base text-primary">
                          table_chart
                        </span>
                        Table « {d.nom_suggere} »
                      </span>
                      <span className="block text-xs text-slate-500 dark:text-slate-400 mt-1">
                        Clé <code className="font-mono">{d.cle}</code> ·{" "}
                        {d.attributs.join(", ")}
                      </span>
                      <span className="block text-[11px] text-slate-400 mt-1 tabular-nums">
                        → {d.lignes.toLocaleString("fr-FR")} ligne
                        {d.lignes > 1 ? "s" : ""} au lieu de{" "}
                        {diagnostic.lignes.toLocaleString("fr-FR")} ·{" "}
                        {d.economie.toLocaleString("fr-FR")} valeurs cessent d&apos;être recopiées
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {diagnostic.constats.length > 0 && (
            <div className="pt-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Signalé, sans correction proposée
              </p>
              <ul className="space-y-1">
                {diagnostic.constats.map((c, i) => (
                  <li key={i} className="text-xs text-slate-500 dark:text-slate-400">
                    · {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {colonnesApercu.length > 0 && (
            <div className="pt-2">
              <button
                onClick={() => setVoirApercu((v) => !v)}
                className="text-xs font-semibold text-primary hover:underline"
              >
                {voirApercu ? "Masquer" : "Voir"} un aperçu des données
              </button>
              {voirApercu && (
                <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-[11px]">
                    <thead className="bg-slate-50 dark:bg-slate-800/60">
                      <tr>
                        {colonnesApercu.map((c) => (
                          <th
                            key={c}
                            dir="auto"
                            className="text-left py-1.5 px-2 font-semibold text-slate-500 whitespace-nowrap"
                          >
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {diagnostic.apercu.slice(0, 6).map((r, i) => (
                        <tr key={i} className="border-t border-slate-100 dark:border-slate-800/60">
                          {colonnesApercu.map((c) => (
                            <td
                              key={c}
                              dir="auto"
                              className="py-1.5 px-2 whitespace-nowrap text-slate-600 dark:text-slate-300"
                            >
                              {r[c] === null || r[c] === undefined ? (
                                <span className="text-slate-400 italic">vide</span>
                              ) : (
                                String(r[c]).slice(0, 28)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Pied */}
        <div className="p-6 pt-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3 flex-wrap">
          <button onClick={onAnnuler} className="text-sm font-semibold text-slate-500">
            Annuler
          </button>
          <div className="flex items-center gap-2">
            {diagnostic.actions.length > 0 && (
              <button
                onClick={() => onValider([], [])}
                className="px-4 py-2 text-sm font-semibold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              >
                Charger sans corriger
              </button>
            )}
            <button
              onClick={() => onValider(choisies, decoupagesChoisis)}
              className="bg-primary text-white rounded-lg px-5 py-2 text-sm font-bold hover:brightness-110"
            >
              {choisies.length + decoupagesChoisis.length > 0
                ? `Appliquer et charger (${choisies.length + decoupagesChoisis.length})`
                : "Charger les données"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
