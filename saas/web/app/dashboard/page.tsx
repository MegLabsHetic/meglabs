"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import Chat from "@/components/Chat";
import DashboardView from "@/components/DashboardView";
import SourcesPanel from "@/components/SourcesPanel";
import { SAMPLE_CSV } from "@/lib/sampleData";
import { LogoMark } from "@/components/Logo";
import SheetPicker from "@/components/SheetPicker";
import ThemeToggle from "@/components/ThemeToggle";
import CleaningDialog, {
  type ActionNettoyage,
  type Decoupage,
  type Diagnostic,
} from "@/components/CleaningDialog";
import Progression from "@/components/Progression";
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
import { fermerSession, lireUtilisateur, type Utilisateur } from "@/lib/session";
import { isAuthenticatedSync } from "@/lib/api";

type Workspace = { id: string; name: string };
type Project = { id: string; name: string; workspace_id: string };
type Me = {
  user: { tier: string };
  usage: { uploads_today: number; ai_queries_today: number };
  limits: { uploads_per_day: number; ai_queries_per_day: number };
};

export default function App() {
  const router = useRouter();
  const [pret, setPret] = useState(false);
  const [compte, setCompte] = useState<Utilisateur | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [schema, setSchema] = useState<any>(null);
  const [tab, setTab] = useState<"chat" | "dashboard" | "sources">("chat");
  const [newName, setNewName] = useState("");
  const [newWorkspace, setNewWorkspace] = useState("");
  const [addingWorkspace, setAddingWorkspace] = useState(false);
  const [targetWorkspace, setTargetWorkspace] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<
    { kind: "project" | "workspace"; id: string; name: string } | null
  >(null);
  // Classeur en attente du choix de sa feuille
  const [classeur, setClasseur] = useState<
    { projet: Project; charge: Charge; feuilles: Feuille[] } | null
  >(null);
  // Fichier en attente de validation du nettoyage
  const [aNettoyer, setANettoyer] = useState<
    { projet: Project; charge: Charge; diagnostic: Diagnostic } | null
  >(null);
  // Suivi vivant du traitement en cours
  const [suivi, setSuivi] = useState<
    { titre: string; sousTitre?: string; etapes: Etape[]; erreur?: string } | null
  >(null);

  /** Remplace la liste d'etapes du suivi affiche. */
  function poserEtapes(etapes: Etape[]) {
    setSuivi((s) => (s ? { ...s, etapes } : s));
  }

  async function refresh() {
    try {
      const [m, w, p] = await Promise.all([
        apiFetch<Me>("/v1/me"),
        apiFetch<Workspace[]>("/v1/workspaces"),
        apiFetch<Project[]>("/v1/projects"),
      ]);
      setMe(m);
      setWorkspaces(w);
      setProjects(p);
      return { workspaces: w, projects: p };
    } catch (e: any) {
      setError(e.message);
      return null;
    }
  }

  // Garde d'acces : sans session, on ne charge rien et on renvoie a la
  // connexion. Le controle cote serveur reste le seul qui protege vraiment ;
  // celui-ci evite juste d'afficher une coquille vide pleine d'erreurs 401.
  useEffect(() => {
    if (!isAuthenticatedSync()) {
      router.replace("/login");
      return;
    }
    setCompte(lireUtilisateur());
    setPret(true);
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function deconnexion() {
    fermerSession();
    router.replace("/login");
  }

  /** Charge le schema de l'entrepot : c'est lui qui dit si le projet a des donnees. */
  async function loadSchema(p: Project) {
    try {
      const s = await apiFetch<any>(`/v1/projects/${p.id}/warehouse/schema`);
      setSchema(s);
      return s;
    } catch (e: any) {
      setSchema({ tables: [] });
      return null;
    }
  }

  async function selectProject(p: Project) {
    setSelected(p);
    setSchema(null);
    setTab("chat");
    setError("");
    await loadSchema(p);
  }

  async function createProject(workspaceId?: string) {
    if (!newName.trim()) return;
    try {
      const p = await apiFetch<Project>("/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: newName, workspace_id: workspaceId || targetWorkspace }),
      });
      setNewName("");
      setTargetWorkspace(null);
      setProjects((prev) => [p, ...prev]);
      selectProject(p);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function createWorkspace() {
    if (!newWorkspace.trim()) return;
    try {
      const w = await apiFetch<Workspace>("/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({ name: newWorkspace }),
      });
      setNewWorkspace("");
      setAddingWorkspace(false);
      setWorkspaces((prev) => [...prev, w]);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function doDelete() {
    if (!confirmDelete) return;
    const { kind, id } = confirmDelete;
    setConfirmDelete(null);
    setError("");
    try {
      await apiFetch(kind === "project" ? `/v1/projects/${id}` : `/v1/workspaces/${id}`, {
        method: "DELETE",
      });
      if (kind === "project" && selected?.id === id) {
        setSelected(null);
        setSchema(null);
      }
      if (kind === "workspace" && selected && projects.some((p) => p.id === selected.id)) {
        const stillThere = projects.find((p) => p.id === selected.id && p.workspace_id !== id);
        if (!stillThere) {
          setSelected(null);
          setSchema(null);
        }
      }
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

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

  async function ingest(
    project: Project,
    charge: Charge,
    sheet?: string,
    actions: ActionNettoyage[] = [],
    decoupage: Decoupage[] = []
  ) {
    setError("");
    setSuivi({
      titre: charge.filename,
      sousTitre: `Chargement dans « ${project.name} »`,
      etapes: planChargement(),
    });
    try {
      const res = await apiFetch<any>(`/v1/projects/${project.id}/sources`, {
        method: "POST",
        body: JSON.stringify({ ...charge, sheet, clean_actions: actions, decoupage }),
      });
      // A partir d'ici, les etapes affichees sont celles que la pipeline
      // publie pendant qu'elle travaille.
      await suivreJob(res.job_id, poserEtapes);

      // Derniere etape, cote navigateur : le projet reflete le nouvel entrepot.
      setSuivi((s) =>
        s
          ? {
              ...s,
              etapes: [
                ...s.etapes,
                { cle: "schema", libelle: "Mise à jour du projet", etat: "cours" },
              ],
            }
          : s
      );
      const sch = await loadSchema(project);
      await refresh();
      const tables = sch?.tables?.length || 0;
      setSuivi((s) =>
        s
          ? {
              ...s,
              etapes: majEtape(
                s.etapes,
                "schema",
                "faite",
                `${tables} table${tables > 1 ? "s" : ""} dans l'entrepôt`
              ),
            }
          : s
      );
      // Laisse voir la derniere coche avant de rendre la main.
      setTimeout(() => setSuivi(null), 900);
    } catch (e: any) {
      echouerSuivi(e.message);
    }
  }

  /**
   * Depot d'un fichier. Un classeur passe d'abord par une inspection : s'il
   * porte plusieurs feuilles exploitables, on demande laquelle importer.
   */
  async function upload(file: File) {
    if (!selected) return;
    setError("");
    // Controle avant lecture : encoder 40 Mo pour se voir refuser ensuite
    // serait une attente pure perte.
    const trop = verifierTaille(file);
    if (trop) {
      setError(trop);
      return;
    }
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
        etapes = majEtape(etapes, "feuilles", "cours");
        poserEtapes(etapes);
        const info = await apiFetch<any>("/v1/files/inspect", {
          method: "POST",
          body: JSON.stringify(charge),
        });
        const feuilles: Feuille[] = info.feuilles || [];
        const utiles = feuilles.filter((f) => !f.vide);
        etapes = majEtape(
          etapes,
          "feuilles",
          "faite",
          `${utiles.length} feuille${utiles.length > 1 ? "s" : ""} exploitable${
            utiles.length > 1 ? "s" : ""
          }`
        );
        if (utiles.length > 1) {
          // La main revient a l'utilisateur : le suivi n'a plus rien a dire
          // tant qu'il n'a pas choisi sa feuille.
          setSuivi(null);
          setClasseur({ projet: selected, charge, feuilles });
          return;
        }
      }
      poserEtapes(etapes);
      await diagnostiquer(selected, charge, undefined, etapes);
    } catch (e: any) {
      echouerSuivi(e.message);
    }
  }

  /**
   * Diagnostic de qualite avant chargement. Deterministe cote serveur : ni
   * appel a un modele, ni quota consomme.
   */
  async function diagnostiquer(
    projet: Project,
    charge: Charge,
    sheet?: string,
    depuis?: Etape[]
  ) {
    // Sans plan fourni, on arrive du choix d'une feuille : la lecture est
    // derriere nous, l'afficher « en cours » serait faux.
    const base = depuis || planApresLecture(charge.filename, sheet);
    setSuivi({
      titre: charge.filename,
      sousTitre: `Préparation pour « ${projet.name} »`,
      etapes: majEtape(base, "diagnostic", "cours"),
    });
    const diagnostic = await apiFetch<Diagnostic>("/v1/files/diagnose", {
      method: "POST",
      body: JSON.stringify({ ...charge, sheet }),
    });
    // Le detail du diagnostic est repris par la fenetre de structuration :
    // l'afficher ici aussi ne ferait que retarder son ouverture.
    setSuivi(null);
    setANettoyer({ projet, charge: { ...charge, ...(sheet ? { sheet } : {}) }, diagnostic });
  }

  async function startWithSample() {
    setError("");
    try {
      let p = selected;
      if (!p) {
        p = await apiFetch<Project>("/v1/projects", {
          method: "POST",
          body: JSON.stringify({ name: "Démo — Ventes" }),
        });
        setProjects((prev) => [p as Project, ...prev]);
        setSelected(p);
        setSchema(null);
        setTab("chat");
      }
      await ingest(p, { filename: "ventes_demo.csv", csv_text: SAMPLE_CSV });
    } catch (e: any) {
      setError(e.message);
    }
  }

  /** Epingle un graphique du chat sur le tableau de bord. */
  async function pinToDashboard(v: any) {
    if (!selected) return;
    try {
      await apiFetch(`/v1/projects/${selected.id}/dashboard`, {
        method: "POST",
        body: JSON.stringify({
          widgets: [{ titre: v.titre, sql: v.sql, viz: v.viz, format: v.format }],
        }),
      });
      setTab("dashboard");
    } catch (e: any) {
      setError(e.message);
    }
  }

  const hasData = (schema?.tables?.length || 0) > 0;
  const tables = schema?.tables || [];

  // Tant que la garde n'a pas tranche, on n'affiche rien : sinon l'ecran
  // d'accueil clignote avant la redirection.
  if (!pret) {
    return <div className="h-screen bg-slate-50 dark:bg-[#0b0f19]" />;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-background-dark flex flex-col">
        <div className="p-5 flex items-center gap-3">
          <LogoMark size={34} id="dv-sidebar" />
          <div>
            {/* Le nom est ecrit ici plutot que via <Logo> : la barre laterale
                a besoin de sa ligne de signature sous le nom. */}
            <h1 className="text-base font-black tracking-[-0.02em] leading-none">
              Data<span className="text-primary">Vox</span>
            </h1>
            <p className="text-slate-500 dark:text-slate-400 text-[11px] mt-1">
              Analyse conversationnelle
            </p>
          </div>
          <div className="ml-auto">
            <ThemeToggle compact />
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-2">
          <div className="flex items-center justify-between px-3 mb-1 mt-2">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Espaces de travail
            </h3>
            <button
              onClick={() => setAddingWorkspace((v) => !v)}
              title="Nouvel espace"
              aria-label="Nouvel espace de travail"
              className="w-5 h-5 rounded flex items-center justify-center text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <span className="material-symbols-outlined text-base">add</span>
            </button>
          </div>

          {addingWorkspace && (
            <div className="px-1 pb-2">
              <input
                autoFocus
                value={newWorkspace}
                onChange={(e) => setNewWorkspace(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") createWorkspace();
                  if (e.key === "Escape") setAddingWorkspace(false);
                }}
                placeholder="Nom de l'espace…"
                className="w-full bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-primary/30"
              />
            </div>
          )}

          {workspaces.map((w) => {
            const inside = projects.filter((p) => p.workspace_id === w.id);
            return (
              <div key={w.id} className="mb-3">
                <div className="group flex items-center gap-1 px-3 py-1">
                  <span className="material-symbols-outlined text-sm text-slate-400">workspaces</span>
                  <span className="text-xs font-bold uppercase tracking-wide text-slate-500 truncate flex-1">
                    {w.name}
                  </span>
                  <button
                    onClick={() => setTargetWorkspace(targetWorkspace === w.id ? null : w.id)}
                    title="Nouveau projet dans cet espace"
                    aria-label={`Nouveau projet dans ${w.name}`}
                    className="w-5 h-5 rounded flex items-center justify-center text-slate-400 opacity-0 group-hover:opacity-100 hover:text-primary"
                  >
                    <span className="material-symbols-outlined text-sm">create_new_folder</span>
                  </button>
                  {workspaces.length > 1 && (
                    <button
                      onClick={() =>
                        setConfirmDelete({ kind: "workspace", id: w.id, name: w.name })
                      }
                      title="Supprimer l'espace"
                      aria-label={`Supprimer l'espace ${w.name}`}
                      className="w-5 h-5 rounded flex items-center justify-center text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500"
                    >
                      <span className="material-symbols-outlined text-sm">delete</span>
                    </button>
                  )}
                </div>

                {targetWorkspace === w.id && (
                  <div className="px-1 pb-1">
                    <input
                      autoFocus
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") createProject(w.id);
                        if (e.key === "Escape") setTargetWorkspace(null);
                      }}
                      placeholder="Nom du projet…"
                      className="w-full bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-primary/30"
                    />
                  </div>
                )}

                {inside.length === 0 && targetWorkspace !== w.id && (
                  <p className="px-3 py-1 text-xs text-slate-400">Aucun projet.</p>
                )}

                {inside.map((p) => (
                  <div
                    key={p.id}
                    className={`group flex items-center rounded-lg transition-colors ${
                      selected?.id === p.id
                        ? "bg-primary/10 text-primary"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    }`}
                  >
                    <button
                      onClick={() => selectProject(p)}
                      className={`flex-1 min-w-0 text-left flex items-center gap-2.5 px-3 py-2 text-sm ${
                        selected?.id === p.id ? "font-semibold" : ""
                      }`}
                    >
                      <span className="material-symbols-outlined text-lg">folder</span>
                      <span className="truncate">{p.name}</span>
                    </button>
                    <button
                      onClick={() => setConfirmDelete({ kind: "project", id: p.id, name: p.name })}
                      title="Supprimer le projet"
                      aria-label={`Supprimer le projet ${p.name}`}
                      className="w-7 h-7 mr-1 rounded flex items-center justify-center text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500 shrink-0"
                    >
                      <span className="material-symbols-outlined text-base">delete</span>
                    </button>
                  </div>
                ))}
              </div>
            );
          })}
        </nav>

        <div className="p-4 pb-0">
          {compte && (
            <div className="flex items-center gap-2.5 mb-3">
              <span className="size-8 shrink-0 rounded-full bg-primary/15 text-primary flex items-center justify-center text-xs font-bold uppercase">
                {(compte.name || compte.email || "?").slice(0, 2)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold truncate">{compte.name || "Mon compte"}</p>
                <p className="text-[10px] text-slate-500 truncate">{compte.email}</p>
              </div>
              <button
                onClick={deconnexion}
                title="Se déconnecter"
                aria-label="Se déconnecter"
                className="w-7 h-7 shrink-0 rounded-md flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <span className="material-symbols-outlined text-base">logout</span>
              </button>
            </div>
          )}
        </div>

        {me && (
          <div className="p-4 pt-0 border-t-0">
            <div className="bg-slate-100 dark:bg-slate-800/50 rounded-xl p-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Plan {me.user.tier}
                </span>
                <span className="material-symbols-outlined text-primary text-lg">bolt</span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {me.usage.ai_queries_today} analyses
                {me.limits.ai_queries_per_day > 0 ? ` / ${me.limits.ai_queries_per_day}` : ""}{" "}
                aujourd&apos;hui
              </p>
            </div>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-[#0b0f19]">
        <header className="h-16 shrink-0 border-b border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-background-dark/70 backdrop-blur-md flex items-center justify-between px-6">
          <div className="flex items-center gap-2 text-sm min-w-0">
            <span className="text-slate-400 truncate">{selected?.name || "Aucun projet"}</span>
            {hasData && (
              <>
                <span className="material-symbols-outlined text-xs text-slate-400">
                  chevron_right
                </span>
                <span className="font-semibold flex items-center gap-1.5 truncate">
                  <span className="material-symbols-outlined text-sm text-primary">database</span>
                  {tables.length === 1
                    ? `${tables[0].name} · ${tables[0].rows.toLocaleString("fr-FR")} lignes`
                    : `${tables.length} tables`}
                </span>
              </>
            )}
          </div>
          {hasData && (
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
              {[
                { k: "chat", icon: "forum", label: "Assistant" },
                { k: "dashboard", icon: "dashboard", label: "Tableau de bord" },
                { k: "sources", icon: "database", label: "Données" },
              ].map((t) => (
                <button
                  key={t.k}
                  onClick={() => setTab(t.k as any)}
                  className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-colors ${
                    tab === t.k
                      ? "bg-white dark:bg-slate-700 text-primary shadow-sm"
                      : "text-slate-500"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm align-middle mr-1">
                    {t.icon}
                  </span>
                  {t.label}
                </button>
              ))}
            </div>
          )}
        </header>

        {error && <div className="px-6 py-2 text-red-500 text-sm bg-red-500/5">{error}</div>}

        <div className="flex-1 overflow-hidden">
          {!selected ? (
            <div className="h-full overflow-y-auto flex flex-col items-center justify-center text-center p-8">
              <div className="max-w-lg w-full">
                <div className="w-16 h-16 rounded-2xl bg-primary/15 text-primary flex items-center justify-center mx-auto mb-5">
                  <span className="material-symbols-outlined text-4xl">waving_hand</span>
                </div>
                <h2 className="text-2xl font-bold">Bienvenue sur DataVox 👋</h2>
                <p className="text-slate-500 dark:text-slate-400 mt-2">
                  Lancez votre première analyse en 3 étapes.
                </p>

                <div className="flex items-center justify-center gap-1.5 my-6 flex-wrap">
                  {["Créer un projet", "Importer des données", "Poser vos questions"].map((s, i) => (
                    <div key={s} className="flex items-center gap-1.5">
                      <span className="w-6 h-6 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold">
                        {i + 1}
                      </span>
                      <span className="text-slate-500 dark:text-slate-400 text-sm">{s}</span>
                      {i < 2 && (
                        <span className="material-symbols-outlined text-slate-300 dark:text-slate-700 text-lg">
                          chevron_right
                        </span>
                      )}
                    </div>
                  ))}
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 text-left shadow-sm">
                  <label className="text-sm font-medium">Nommez votre premier projet</label>
                  <div className="flex gap-2 mt-2">
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && createProject()}
                      placeholder="Ex : Analyse des ventes 2026"
                      className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary/30"
                    />
                    <button
                      onClick={() => createProject()}
                      className="bg-primary text-white rounded-lg px-5 font-bold hover:brightness-110 transition"
                    >
                      Créer
                    </button>
                  </div>
                  <div className="relative my-5 text-center">
                    <div className="absolute inset-x-0 top-1/2 h-px bg-slate-200 dark:bg-slate-800" />
                    <span className="relative text-xs text-slate-400 bg-white dark:bg-slate-900 px-3">
                      ou
                    </span>
                  </div>
                  <button
                    onClick={startWithSample}
                    disabled={!!suivi}
                    className="w-full inline-flex items-center justify-center gap-2 border border-slate-200 dark:border-slate-700 rounded-lg py-2.5 text-sm font-bold hover:border-primary transition disabled:opacity-60"
                  >
                    <span className="material-symbols-outlined text-lg text-primary">bolt</span>
                    Essayer avec un jeu de données d&apos;exemple
                  </button>
                </div>
              </div>
            </div>
          ) : !hasData ? (
            <div className="h-full flex flex-col items-center justify-center p-8">
              <div className="w-full max-w-lg">
                <p className="text-center text-sm mb-3">
                  <span className="text-primary font-bold">Étape 2 sur 3</span>{" "}
                  <span className="text-slate-400">· Importez vos données</span>
                </p>
                <label className="cursor-pointer block">
                  <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl p-12 text-center hover:border-primary transition-colors bg-white/50 dark:bg-slate-900/30">
                    <div className="w-14 h-14 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto mb-4">
                      <span className="material-symbols-outlined text-3xl">upload_file</span>
                    </div>
                    <p className="font-bold text-lg">Glissez votre fichier</p>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                      CSV ou Excel (.xlsx, .xls) — nettoyé, typé et chargé dans
                      l&apos;entrepôt du projet
                    </p>
                    <input
                      type="file"
                      accept={EXTENSIONS_ACCEPTEES}
                      className="hidden"
                      onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                    />
                  </div>
                </label>
                <div className="text-center mt-4">
                  <button
                    onClick={startWithSample}
                    disabled={!!suivi}
                    className="text-sm text-primary font-semibold hover:underline disabled:opacity-60"
                  >
                    ou charger un jeu de données d&apos;exemple
                  </button>
                </div>
              </div>
            </div>
          ) : tab === "chat" ? (
            <Chat projectId={selected.id} schema={schema} onPin={pinToDashboard} />
          ) : tab === "dashboard" ? (
            <DashboardView projectId={selected.id} />
          ) : (
            <SourcesPanel projectId={selected.id} onChanged={() => loadSchema(selected)} />
          )}
        </div>
      </main>

      {/* Suivi vivant : ce qui se passe pendant que le fichier est traite. */}
      {suivi && (
        <Progression
          titre={suivi.titre}
          sousTitre={suivi.sousTitre}
          etapes={suivi.etapes}
          erreur={suivi.erreur}
          onFermer={() => setSuivi(null)}
        />
      )}

      {classeur && (
        <SheetPicker
          fichier={classeur.charge.filename}
          feuilles={classeur.feuilles}
          onAnnuler={() => setClasseur(null)}
          onChoisir={(nom) => {
            const { projet, charge } = classeur;
            setClasseur(null);
            diagnostiquer(projet, charge, nom).catch((e) => echouerSuivi(e.message));
          }}
        />
      )}

      {aNettoyer && (
        <CleaningDialog
          fichier={aNettoyer.charge.filename}
          diagnostic={aNettoyer.diagnostic}
          onAnnuler={() => setANettoyer(null)}
          onValider={(actions, decoupages) => {
            const { projet, charge } = aNettoyer;
            setANettoyer(null);
            ingest(projet, charge, (charge as any).sheet, actions, decoupages);
          }}
        />
      )}

      {/* Confirmation de suppression : irreversible, donc jamais en un clic. */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-sm w-full p-6">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-2xl text-red-500">warning</span>
              <div>
                <h3 className="font-bold">
                  Supprimer {confirmDelete.kind === "project" ? "le projet" : "l'espace"} «{" "}
                  {confirmDelete.name} » ?
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                  {confirmDelete.kind === "project"
                    ? "Les sources, l'entrepôt de données et le tableau de bord de ce projet seront définitivement supprimés."
                    : "Tous les projets de cet espace, leurs données et leurs tableaux de bord seront définitivement supprimés."}
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 text-sm font-semibold text-slate-500"
              >
                Annuler
              </button>
              <button
                onClick={doDelete}
                className="bg-red-500 text-white rounded-lg px-5 py-2 text-sm font-bold hover:brightness-110"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
