"use client";

import { useEffect, useState } from "react";
import { apiFetch, uiLangue } from "@/lib/api";
import SchemaDiagram from "@/components/SchemaDiagram";
import SheetPicker from "@/components/SheetPicker";
import Progression from "@/components/Progression";
import CleaningDialog, {
  type ActionNettoyage,
  type Decoupage,
  type Diagnostic,
} from "@/components/CleaningDialog";
import {
  majEtape,
  planAnalyse,
  planApresLecture,
  planChargement,
  suivreJob,
  tailleLisible,
  type Etape,
} from "@/lib/progression";
import {
  EXTENSIONS_ACCEPTEES,
  preparer,
  verifierTaille,
  type Charge,
  type Feuille,
} from "@/lib/fichier";

/**
 * Sources du projet et mise a jour des donnees.
 *
 * Le rafraichissement se fait en deux temps : on controle d'abord la structure
 * du fichier (aucune donnee touchee), puis l'utilisateur valide en connaissance
 * de cause. Un fichier qui ne correspond pas du tout est refuse avec une
 * explication, pas avec une erreur technique.
 */

type Source = {
  id: string;
  filename: string;
  table_name: string;
  column_map: Record<string, string> | null;
  row_count: number | null;
  status: string;
  ingested_at: string | null;
};

type Diff = {
  verdict: "identical" | "compatible" | "partial" | "incompatible" | "new";
  renames: Record<string, string>;
  missing: string[];
  extra: string[];
  issues: string[];
  explication?: string;
  analyse_ia?: boolean;
};

const VERDICT_UI: Record<string, { label: string; tone: string; icon: string }> = {
  identical: { label: "Structure identique", tone: "text-emerald-600 dark:text-emerald-500", icon: "check_circle" },
  compatible: { label: "Structure compatible", tone: "text-emerald-600 dark:text-emerald-500", icon: "check_circle" },
  partial: { label: "Structure partiellement compatible", tone: "text-amber-600 dark:text-amber-500", icon: "warning" },
  incompatible: { label: "Fichier incompatible", tone: "text-red-500", icon: "block" },
  new: { label: "Nouvelle table", tone: "text-slate-500", icon: "info" },
};

function RefreshDialog({
  source,
  diff,
  onClose,
  onApply,
}: {
  source: Source;
  diff: Diff;
  onClose: () => void;
  onApply: (mode: string, renames: Record<string, string>) => Promise<void>;
}) {
  const [mode, setMode] = useState("replace");
  const [busy, setBusy] = useState(false);
  const ui = VERDICT_UI[diff.verdict] || VERDICT_UI.partial;
  const blocked = diff.verdict === "incompatible";

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-lg w-full p-6 max-h-[85vh] overflow-y-auto">
        <div className="flex items-start gap-3">
          <span className={`material-symbols-outlined text-2xl ${ui.tone}`}>{ui.icon}</span>
          <div className="min-w-0">
            <h3 className="font-bold">{ui.label}</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Contrôle de « {source.filename} » avant mise à jour
              {diff.analyse_ia && " · analyse approfondie"}
            </p>
          </div>
        </div>

        {diff.explication && (
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-4 leading-relaxed">
            {diff.explication}
          </p>
        )}

        {diff.issues?.length > 0 && (
          <ul className="mt-4 space-y-1.5 text-sm">
            {diff.issues.map((issue, i) => (
              <li key={i} className="flex gap-2 text-slate-600 dark:text-slate-300">
                <span className="material-symbols-outlined text-sm text-slate-400 mt-0.5">
                  arrow_right
                </span>
                {issue}
              </li>
            ))}
          </ul>
        )}

        {Object.keys(diff.renames || {}).length > 0 && (
          <div className="mt-4 bg-slate-50 dark:bg-slate-800/60 rounded-lg p-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Corrections appliquées
            </p>
            {Object.entries(diff.renames).map(([from, to]) => (
              <p key={from} className="text-sm font-mono">
                {from} <span className="text-slate-400">→</span> {to}
              </p>
            ))}
          </div>
        )}

        {!blocked && (
          <div className="mt-5">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 flex gap-2">
              <span className="material-symbols-outlined text-base text-primary shrink-0">
                autorenew
              </span>
              Les corrections et le découpage retenus à l&apos;import sont rejoués sur ce
              fichier : la source garde la même forme, et vos indicateurs continuent de
              calculer.
            </p>
            <p className="text-sm font-semibold mb-2">Que faire des données existantes ?</p>
            <div className="space-y-2">
              {[
                { v: "replace", t: "Remplacer", d: "Les anciennes lignes sont écrasées par le fichier." },
                { v: "append", t: "Ajouter", d: "Les lignes du fichier s'ajoutent à celles déjà présentes." },
              ].map((o) => (
                <label
                  key={o.v}
                  className={`flex gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    mode === o.v
                      ? "border-primary bg-primary/5"
                      : "border-slate-200 dark:border-slate-700"
                  }`}
                >
                  <input
                    type="radio"
                    checked={mode === o.v}
                    onChange={() => setMode(o.v)}
                    className="mt-0.5 text-primary focus:ring-primary/30"
                  />
                  <span>
                    <span className="text-sm font-semibold block">{o.t}</span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{o.d}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm font-semibold text-slate-500">
            {blocked ? "Fermer" : "Annuler"}
          </button>
          {!blocked && (
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await onApply(mode, diff.renames || {});
                } finally {
                  setBusy(false);
                }
              }}
              className="bg-primary text-white rounded-lg px-5 py-2 text-sm font-bold hover:brightness-110 disabled:opacity-50"
            >
              {busy ? "Mise à jour…" : "Mettre à jour les données"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SourcesPanel({
  projectId,
  onChanged,
}: {
  projectId: string;
  onChanged: () => void;
}) {
  const [sources, setSources] = useState<Source[]>([]);
  const [schema, setSchema] = useState<any>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [pending, setPending] = useState<{ source: Source; charge: Charge; diff: Diff } | null>(null);
  // Suivi vivant des traitements qui passent par la pipeline
  const [suivi, setSuivi] = useState<
    { titre: string; sousTitre?: string; etapes: Etape[]; erreur?: string } | null
  >(null);
  // Fichier en attente de validation des corrections
  const [aNettoyer, setANettoyer] = useState<
    { charge: Charge; diagnostic: Diagnostic } | null
  >(null);

  /** L'etape en cours porte l'echec : c'est la qu'on s'est arrete. */
  function echouerSuivi(message: string) {
    setSuivi((s) =>
      s
        ? {
            ...s,
            erreur: message,
            etapes: s.etapes.map((e) => (e.etat === "cours" ? { ...e, etat: "echec" } : e)),
          }
        : s
    );
    setError(message);
  }
  // Classeur en attente du choix de sa feuille. `source` non nul = mise a jour
  // d'une source existante ; nul = ajout d'une nouvelle source.
  const [classeur, setClasseur] = useState<
    { source: Source | null; charge: Charge; feuilles: Feuille[] } | null
  >(null);

  /** Un classeur a plusieurs feuilles exploitables : on demande laquelle. */
  async function feuilleAChoisir(charge: Charge): Promise<Feuille[] | null> {
    if (!charge.file_base64) return null;
    const info = await apiFetch<any>("/v1/files/inspect", {
      method: "POST",
      body: JSON.stringify(charge),
    });
    const feuilles: Feuille[] = info.feuilles || [];
    return feuilles.filter((f) => !f.vide).length > 1 ? feuilles : null;
  }

  async function load() {
    try {
      const [liste, sch] = await Promise.all([
        apiFetch<Source[]>(`/v1/projects/${projectId}/sources`),
        apiFetch<any>(`/v1/projects/${projectId}/warehouse/schema`),
      ]);
      setSources(liste);
      setSchema(sch);
    } catch (e: any) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  /**
   * Attend la fin d'un job en montrant ou en est la pipeline. Le suivi se
   * ferme tout seul en cas de succes ; en cas d'echec il reste ouvert sur
   * l'etape fautive.
   */
  async function suivrePipeline(jobId: string, titre: string, sousTitre: string) {
    setSuivi({ titre, sousTitre, etapes: planChargement() });
    try {
      const job = await suivreJob(jobId, (etapes) =>
        setSuivi((s) => (s ? { ...s, etapes } : s))
      );
      setTimeout(() => setSuivi(null), 900);
      return job;
    } catch (e: any) {
      setSuivi((s) =>
        s
          ? {
              ...s,
              erreur: e.message,
              etapes: s.etapes.map((x) => (x.etat === "cours" ? { ...x, etat: "echec" } : x)),
            }
          : s
      );
      throw e;
    }
  }

  async function checkRefresh(source: Source, file: File, sheet?: string) {
    setError("");
    const trop = verifierTaille(file);
    if (trop) return setError(trop);
    setStatus(`Contrôle de la structure de ${file.name}…`);
    try {
      const charge = await preparer(file);
      if (!sheet) {
        const feuilles = await feuilleAChoisir(charge);
        if (feuilles) {
          setStatus("");
          setClasseur({ source, charge, feuilles });
          return;
        }
      }
      const avecFeuille = { ...charge, sheet };
      const diff = await apiFetch<Diff>(`/v1/sources/${source.id}/refresh/check`, {
        method: "POST",
        body: JSON.stringify({ ...avecFeuille, langue: uiLangue() }),
      });
      setPending({ source, charge: avecFeuille, diff });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStatus("");
    }
  }

  /** Reprend le controle apres le choix d'une feuille. */
  async function poursuivreApresFeuille(nom: string) {
    if (!classeur) return;
    const { source, charge } = classeur;
    setClasseur(null);
    const avecFeuille = { ...charge, sheet: nom };
    try {
      if (source) {
        setStatus("Contrôle en cours…");
        const diff = await apiFetch<Diff>(`/v1/sources/${source.id}/refresh/check`, {
          method: "POST",
          body: JSON.stringify({ ...avecFeuille, langue: uiLangue() }),
        });
        setPending({ source, charge: avecFeuille, diff });
      } else {
        // Nouvelle source : elle passe par le diagnostic, comme un import.
        await diagnostiquer(avecFeuille, planApresLecture(charge.filename, nom));
      }
    } catch (e: any) {
      echouerSuivi(e.message);
    } finally {
      setStatus("");
    }
  }

  async function applyRefresh(mode: string, renames: Record<string, string>) {
    if (!pending) return;
    const { source, charge } = pending;
    setPending(null);
    try {
      const res = await apiFetch<any>(`/v1/sources/${source.id}/refresh`, {
        method: "POST",
        body: JSON.stringify({ ...charge, mode, renames }),
      });
      await suivrePipeline(
        res.job_id,
        charge.filename,
        `Mise à jour de « ${source.table_name} »`
      );
      await load();
      onChanged();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function envoyerSource(
    charge: Charge,
    actions: ActionNettoyage[] = [],
    decoupages: Decoupage[] = []
  ) {
    const res = await apiFetch<any>(`/v1/projects/${projectId}/sources`, {
      method: "POST",
      body: JSON.stringify({ ...charge, clean_actions: actions, decoupage: decoupages }),
    });
    await suivrePipeline(res.job_id, charge.filename, "Ajout d'une source au projet");
    await load();
    onChanged();
  }

  /**
   * Diagnostic de structure et de qualite avant chargement — le meme que sur
   * l'import initial. Une source ajoutee ici arrivait sinon brute dans
   * l'entrepot, avec ses doublons et ses nombres restes en texte.
   */
  async function diagnostiquer(charge: Charge, etapes: Etape[]) {
    setSuivi({
      titre: charge.filename,
      sousTitre: "Préparation de la source",
      etapes: majEtape(etapes, "diagnostic", "cours"),
    });
    const diagnostic = await apiFetch<Diagnostic>("/v1/files/diagnose", {
      method: "POST",
      body: JSON.stringify(charge),
    });
    setSuivi(null);
    setANettoyer({ charge, diagnostic });
  }

  async function addSource(file: File) {
    setError("");
    const trop = verifierTaille(file);
    if (trop) return setError(trop);
    setSuivi({
      titre: file.name,
      sousTitre: tailleLisible(file.size),
      etapes: planAnalyse(file.name),
    });
    try {
      const charge = await preparer(file);
      let etapes = majEtape(
        planAnalyse(file.name),
        "lecture",
        "faite",
        charge.file_base64 ? "classeur Excel" : "fichier CSV"
      );
      if (charge.file_base64) {
        setSuivi((s) => (s ? { ...s, etapes: majEtape(etapes, "feuilles", "cours") } : s));
        const feuilles = await feuilleAChoisir(charge);
        etapes = majEtape(etapes, "feuilles", "faite");
        if (feuilles) {
          setSuivi(null);
          setClasseur({ source: null, charge, feuilles });
          return;
        }
      }
      await diagnostiquer(charge, etapes);
    } catch (e: any) {
      echouerSuivi(e.message);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      {error && (
        <div className="mb-4 text-red-500 text-sm bg-red-500/5 rounded-lg px-4 py-2">{error}</div>
      )}
      {status && (
        <p className="mb-4 text-primary text-sm font-medium flex items-center gap-2">
          <span className="spinner" style={{ borderColor: "rgba(13,89,242,0.3)", borderTopColor: "#0d59f2" }} />
          {status}
        </p>
      )}

      <div className="space-y-3">
        {sources.map((s) => (
          <div
            key={s.id}
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 flex-wrap"
          >
            <div className="min-w-0">
              <p className="font-semibold text-sm flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-lg">table_chart</span>
                {s.filename}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                table <code className="font-mono">{s.table_name}</code> ·{" "}
                {s.row_count?.toLocaleString("fr-FR") ?? "—"} lignes
                {s.ingested_at && ` · mise à jour le ${s.ingested_at.slice(0, 10)}`}
              </p>
            </div>
            <label className="cursor-pointer shrink-0">
              <span className="inline-flex items-center gap-1.5 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs font-bold hover:border-primary transition-colors">
                <span className="material-symbols-outlined text-base">sync</span>
                Mettre à jour
              </span>
              <input
                type="file"
                accept={EXTENSIONS_ACCEPTEES}
                className="hidden"
                onChange={(e) => e.target.files?.[0] && checkRefresh(s, e.target.files[0])}
              />
            </label>
          </div>
        ))}
      </div>

      <label className="cursor-pointer block mt-4">
        <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-6 text-center hover:border-primary transition-colors">
          <span className="material-symbols-outlined text-2xl text-primary">add</span>
          <p className="text-sm font-semibold mt-1">Ajouter une source</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            CSV ou Excel — chaque fichier devient une table de plus dans l&apos;entrepôt
          </p>
        </div>
        <input
          type="file"
          accept={EXTENSIONS_ACCEPTEES}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && addSource(e.target.files[0])}
        />
      </label>

      {/* Schema de l'entrepot : ce que contiennent reellement les donnees
          chargees, juste sous la zone de mise a jour. */}
      {schema?.tables?.length > 0 && (
        <div className="mt-8">
          <div className="flex items-baseline justify-between gap-4 flex-wrap mb-1">
            <h3 className="font-bold">Structure de l&apos;entrepôt</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {schema.tables.length} table{schema.tables.length > 1 ? "s" : ""}
              {" · "}
              {schema.tables.reduce((n: number, t: any) => n + t.columns.length, 0)} colonnes
              {schema.relations?.length > 0 &&
                ` · ${schema.relations.length} lien${schema.relations.length > 1 ? "s" : ""} détecté${
                  schema.relations.length > 1 ? "s" : ""
                }`}
            </p>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
            Les liens entre tables sont déduits des données elles-mêmes : un lien
            n&apos;est affiché que si les valeurs correspondent réellement.
          </p>
          <div className="bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
            <SchemaDiagram tables={schema.tables} relations={schema.relations || []} />
          </div>
        </div>
      )}

      {classeur && (
        <SheetPicker
          fichier={classeur.charge.filename}
          feuilles={classeur.feuilles}
          onAnnuler={() => setClasseur(null)}
          onChoisir={poursuivreApresFeuille}
        />
      )}

      {pending && (
        <RefreshDialog
          source={pending.source}
          diff={pending.diff}
          onClose={() => setPending(null)}
          onApply={applyRefresh}
        />
      )}

      {aNettoyer && (
        <CleaningDialog
          fichier={aNettoyer.charge.filename}
          diagnostic={aNettoyer.diagnostic}
          onAnnuler={() => setANettoyer(null)}
          onValider={(actions, decoupages) => {
            const { charge } = aNettoyer;
            setANettoyer(null);
            envoyerSource(charge, actions, decoupages).catch((e) => echouerSuivi(e.message));
          }}
        />
      )}

      {suivi && (
        <Progression
          titre={suivi.titre}
          sousTitre={suivi.sousTitre}
          etapes={suivi.etapes}
          erreur={suivi.erreur}
          onFermer={() => setSuivi(null)}
        />
      )}
    </div>
  );
}
