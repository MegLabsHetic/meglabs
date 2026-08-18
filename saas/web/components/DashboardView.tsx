"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, uiLangue } from "@/lib/api";
import SqlChart, { Tile } from "@/components/SqlChart";
import { VIZ_LABELS } from "@/lib/sqlViz";
import type { Apparence } from "@/lib/chartTheme";
import ReportButton from "@/components/ReportButton";

/**
 * Tableau de bord adosse a l'entrepot.
 *
 * Chaque indicateur est une SPEC (une requete SQL) enregistree en base, jamais
 * un resultat fige : rouvrir le tableau de bord rejoue le SQL sur les donnees
 * du moment et ne coute aucun appel au moteur. Un rafraichissement des donnees se
 * repercute donc tout seul.
 */

type Widget = {
  id: string;
  title: string;
  sql: string;
  viz: string;
  format: string;
  position: number;
  /** Couleur, pics entoures, etiquettes — demandes dans l'atelier. */
  style?: Apparence | null;
};

type Card = { widget: Widget; data: any; erreur: string | null };

const PRIMARY = "#0d59f2";

/** Editeur d'un indicateur : le SQL reste modifiable a la main. */
function WidgetEditor({
  widget,
  onSave,
  onCancel,
}: {
  widget: Widget;
  onSave: (patch: Partial<Widget>) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(widget.title);
  const [sql, setSql] = useState(widget.sql);
  const [viz, setViz] = useState(widget.viz);
  const [format, setFormat] = useState(widget.format);
  const [style, setStyle] = useState<Apparence>(widget.style || {});
  const [busy, setBusy] = useState(false);
  // Ce que l'atelier sait faire se fait aussi a la main : sans cela, une
  // couleur posee par la conversation ne serait plus reprenable ici.
  const couleurs = ["bleu", "orange", "aqua", "jaune", "magenta", "vert", "violet", "rouge"];
  const slot = (n: string) => `var(--viz-series-${couleurs.indexOf(n) + 1})`;

  return (
    <div className="bg-white dark:bg-slate-900 border-2 border-primary/40 rounded-xl p-4 space-y-3">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-2 text-sm font-semibold focus:ring-2 focus:ring-primary/30"
      />
      <textarea
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        rows={5}
        spellCheck={false}
        className="w-full bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-2 text-[11px] font-mono leading-relaxed focus:ring-2 focus:ring-primary/30"
      />
      <div className="flex flex-wrap gap-2">
        <select
          value={viz}
          onChange={(e) => setViz(e.target.value)}
          className="bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-1.5 text-xs"
        >
          {Object.entries(VIZ_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={format}
          onChange={(e) => setFormat(e.target.value)}
          className="bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-1.5 text-xs"
        >
          <option value="nombre">Nombre</option>
          <option value="monetaire">Monétaire</option>
          <option value="pourcentage">Pourcentage</option>
        </select>
      </div>

      {/* Apparence */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span className="text-xs text-slate-500 dark:text-slate-400">Couleur</span>
        <button
          onClick={() => setStyle({ ...style, couleur: null })}
          title="Palette par défaut"
          aria-label="Palette par défaut"
          className={`w-5 h-5 rounded-full border text-[10px] leading-none flex items-center justify-center ${
            style.couleur ? "border-slate-300 dark:border-slate-600 text-slate-400" : "border-primary text-primary"
          }`}
        >
          A
        </button>
        {couleurs.map((c) => (
          <button
            key={c}
            onClick={() => setStyle({ ...style, couleur: c })}
            title={c}
            aria-label={`Couleur ${c}`}
            style={{ background: slot(c) }}
            className={`w-5 h-5 rounded-full transition-transform ${
              style.couleur === c ? "ring-2 ring-offset-2 ring-slate-400 dark:ring-offset-slate-900" : ""
            }`}
          />
        ))}

        <select
          value={style.entourer || ""}
          onChange={(e) =>
            setStyle({ ...style, entourer: (e.target.value || null) as Apparence["entourer"] })
          }
          className="bg-slate-100 dark:bg-slate-800 border-none rounded-lg px-3 py-1.5 text-xs"
        >
          <option value="">Rien à entourer</option>
          <option value="max">Entourer le pic</option>
          <option value="min">Entourer le creux</option>
          <option value="extremes">Entourer les deux</option>
        </select>

        <label className="text-xs flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={!!style.etiquettes}
            onChange={(e) => setStyle({ ...style, etiquettes: e.target.checked })}
            className="rounded text-primary focus:ring-primary/30"
          />
          Valeurs affichées
        </label>

        <div className="flex-1" />
        <button onClick={onCancel} className="px-3 py-1.5 text-xs font-semibold text-slate-500">
          Annuler
        </button>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onSave({ title, sql, viz, format, style });
            } finally {
              setBusy(false);
            }
          }}
          className="bg-primary text-white rounded-lg px-4 py-1.5 text-xs font-bold hover:brightness-110 disabled:opacity-50"
        >
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}

export default function DashboardView({ projectId }: { projectId: string }) {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [proposed, setProposed] = useState<any[] | null>(null);
  const [picked, setPicked] = useState<Record<number, boolean>>({});

  // Atelier : la conversation qui fait evoluer le tableau de bord. Ferme par
  // defaut — la place revient aux indicateurs, pas au panneau.
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function load() {
    setError("");
    try {
      const res = await apiFetch<any>(`/v1/projects/${projectId}/dashboard`);
      setCards(res.widgets || []);
    } catch (e: any) {
      setError(e.message);
      setCards([]);
    }
  }

  useEffect(() => {
    setProposed(null);
    setMessages([]);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatBusy]);

  async function propose() {
    setBusy(true);
    setError("");
    try {
      const res = await apiFetch<any>(`/v1/projects/${projectId}/dashboard/propose`, {
        method: "POST",
        body: JSON.stringify({ langue: uiLangue() }),
      });
      const list = res.kpis || [];
      setProposed(list);
      setPicked(Object.fromEntries(list.map((_: any, i: number) => [i, true])));
      if (list.length === 0) setError("Aucun indicateur calculable n'a pu être proposé pour ces données.");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmProposal() {
    if (!proposed) return;
    setBusy(true);
    try {
      const widgets = proposed
        .filter((_, i) => picked[i])
        .map((k) => ({ titre: k.titre, sql: k.sql, viz: k.viz, format: k.format }));
      await apiFetch(`/v1/projects/${projectId}/dashboard`, {
        method: "POST",
        body: JSON.stringify({ widgets, replace: true }),
      });
      setProposed(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveWidget(id: string, patch: Partial<Widget>) {
    await apiFetch(`/v1/widgets/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
    setEditing(null);
    await load();
  }

  async function removeWidget(id: string) {
    await apiFetch(`/v1/widgets/${id}`, { method: "DELETE" });
    await load();
  }

  async function sendChat(text: string) {
    const msg = text.trim();
    if (!msg || chatBusy) return;
    setInput("");
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setChatBusy(true);
    try {
      const res = await apiFetch<any>(`/v1/projects/${projectId}/dashboard/chat`, {
        method: "POST",
        body: JSON.stringify({ message: msg, history }),
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reponse || "", rejetees: res.rejetees || [] },
      ]);
      await load();
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: "assistant", content: "⚠️ " + e.message }]);
    } finally {
      setChatBusy(false);
    }
  }

  // ── Choix des indicateurs proposes ──────────────
  if (proposed) {
    const count = Object.values(picked).filter(Boolean).length;
    return (
      <div className="h-full overflow-y-auto p-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 mb-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="font-semibold">{proposed.length} indicateurs proposés</p>
            <p className="text-slate-500 dark:text-slate-400 text-sm">
              Décochez ce qui ne vous sert pas. Chaque requête a déjà été exécutée sur vos données.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setProposed(null)}
              className="px-4 py-2 text-sm font-semibold text-slate-500"
            >
              Annuler
            </button>
            <button
              onClick={confirmProposal}
              disabled={busy || count === 0}
              className="bg-primary text-white rounded-lg px-5 py-2 text-sm font-bold hover:brightness-110 disabled:opacity-50"
            >
              Créer le tableau de bord ({count})
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {proposed.map((k, i) => (
            <div key={i} className="relative">
              <label className="absolute top-4 left-4 z-10 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!picked[i]}
                  onChange={(e) => setPicked({ ...picked, [i]: e.target.checked })}
                  aria-label={`Garder ${k.titre}`}
                  className="rounded text-primary focus:ring-primary/30"
                />
              </label>
              <div className={picked[i] ? "" : "opacity-45"}>
                <SqlChart
                  title={`    ${k.titre}`}
                  result={k.apercu}
                  viz={k.viz}
                  format={k.format}
                  sql={k.sql}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const tiles = (cards || []).filter(
    (c) => c.widget.viz === "tuile" && !c.erreur && editing !== c.widget.id
  );
  const rest = (cards || []).filter((c) => !tiles.includes(c));

  return (
    // `relative` : l'atelier flotte au-dessus des indicateurs plutot que de
    // leur prendre un tiers de la largeur en permanence.
    <div className="h-full overflow-hidden relative">
      {/* Indicateurs */}
      <div className="h-full overflow-y-auto p-6 pb-24">
        {error && (
          <div className="mb-4 text-red-500 text-sm bg-red-500/5 rounded-lg px-4 py-2">{error}</div>
        )}

        {cards !== null && cards.length > 0 && (
          <div className="flex justify-end mb-4">
            <ReportButton projectId={projectId} variante="discret" onErreur={setError} />
          </div>
        )}

        {cards === null ? (
          <p className="text-slate-400 text-sm">Chargement…</p>
        ) : cards.length === 0 ? (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-8 text-center">
            <p className="font-semibold mb-1">Composez votre tableau de bord</p>
            <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
              Des indicateurs sont proposés à partir de vos données —{" "}
              <b>vous choisissez ceux que vous gardez</b>. Ensuite, le bouton « Affiner » en bas à
              droite fait évoluer le tableau de bord à la demande.
            </p>
            <button
              onClick={propose}
              disabled={busy}
              className="bg-primary text-white rounded-lg px-5 py-2.5 text-sm font-bold hover:brightness-110 disabled:opacity-50 inline-flex items-center gap-2"
            >
              {busy ? (
                <>
                  <span className="spinner" />
                  Analyse…
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-lg">auto_awesome</span>
                  Proposer des indicateurs
                </>
              )}
            </button>
          </div>
        ) : (
          <>
            {tiles.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                {tiles.map((c) => (
                  <div key={c.widget.id} className="relative group">
                    <Tile
                      title={c.widget.title}
                      value={c.data?.rows?.[0] ? Number(Object.values(c.data.rows[0])[0]) : null}
                      format={c.widget.format}
                      erreur={c.erreur}
                    />
                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-0.5">
                      <button
                        onClick={() => setEditing(c.widget.id)}
                        title="Modifier"
                        aria-label="Modifier l'indicateur"
                        className="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <span className="material-symbols-outlined text-sm">edit</span>
                      </button>
                      <button
                        onClick={() => removeWidget(c.widget.id)}
                        title="Supprimer"
                        aria-label="Supprimer l'indicateur"
                        className="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <span className="material-symbols-outlined text-sm">delete</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {rest.map((c) =>
                editing === c.widget.id ? (
                  <WidgetEditor
                    key={c.widget.id}
                    widget={c.widget}
                    onCancel={() => setEditing(null)}
                    onSave={(patch) => saveWidget(c.widget.id, patch)}
                  />
                ) : (
                  <SqlChart
                    key={c.widget.id}
                    title={c.widget.title}
                    result={c.data}
                    viz={c.widget.viz}
                    format={c.widget.format}
                    erreur={c.erreur}
                    sql={c.widget.sql}
                    style={c.widget.style}
                    actions={
                      <>
                        <button
                          onClick={() => setEditing(c.widget.id)}
                          title="Modifier"
                          aria-label="Modifier l'indicateur"
                          className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                          <span className="material-symbols-outlined text-base">edit</span>
                        </button>
                        <button
                          onClick={() => removeWidget(c.widget.id)}
                          title="Supprimer"
                          aria-label="Supprimer l'indicateur"
                          className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                          <span className="material-symbols-outlined text-base">delete</span>
                        </button>
                      </>
                    }
                  />
                )
              )}
            </div>
          </>
        )}
      </div>

      {/*
        L'atelier : une conversation qui fait evoluer le tableau de bord.
        Pastille discrete au repos, panneau ancre au-dessus des indicateurs
        une fois ouvert — la largeur reste aux graphiques.
      */}
      {chatOpen ? (
        <aside className="absolute bottom-4 right-4 z-30 w-[min(380px,calc(100%-2rem))] h-[min(70vh,560px)] flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
          <div className="h-12 shrink-0 px-4 flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2 min-w-0">
              <span className="material-symbols-outlined text-primary text-lg">auto_awesome</span>
              <span className="text-sm font-bold truncate">Affiner le tableau de bord</span>
            </div>
            <button
              onClick={() => setChatOpen(false)}
              aria-label="Réduire l'atelier"
              className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 shrink-0"
            >
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && (
              <div className="text-sm text-slate-500 dark:text-slate-400 space-y-3">
                <p>
                  Dites ce que vous voulez voir : l&apos;indicateur apparaît, change de calcul ou
                  disparaît, tout de suite.
                </p>
                <div className="space-y-1.5">
                  {[
                    "Ajoute le panier moyen par pays",
                    "Le chiffre d'affaires doit exclure les commandes annulées",
                    "Enlève la répartition par statut",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => sendChat(s)}
                      className="w-full text-left px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[85%] bg-primary text-white px-3 py-2 rounded-xl rounded-tr-none text-sm"
                    : "max-w-[92%] bg-slate-100 dark:bg-slate-800 px-3 py-2 rounded-xl rounded-tl-none text-sm"
                }
              >
                {m.content}
                {m.rejetees?.length > 0 && (
                  <ul className="mt-2 text-xs text-amber-600 dark:text-amber-500 list-disc pl-4">
                    {m.rejetees.map((r: any, j: number) => (
                      <li key={j}>
                        {r.titre || "Indicateur"} — non appliqué : {r.erreur}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {chatBusy && (
              <div className="text-sm text-slate-400 flex items-center gap-2">
                <span
                  className="spinner"
                  style={{ borderColor: "rgba(100,116,139,0.4)", borderTopColor: PRIMARY }}
                />
                Application…
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="p-3 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-end gap-2 p-1.5 pl-3 bg-slate-100 dark:bg-slate-800 rounded-xl">
              <textarea
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendChat(input);
                  }
                }}
                placeholder="Décrivez l'indicateur voulu…"
                className="flex-1 py-1.5 text-sm bg-transparent border-none focus:ring-0 resize-none max-h-24 outline-none"
              />
              <button
                onClick={() => sendChat(input)}
                disabled={chatBusy || !input.trim()}
                aria-label="Envoyer"
                className="w-8 h-8 bg-primary text-white rounded-lg flex items-center justify-center hover:brightness-110 disabled:opacity-40 shrink-0"
              >
                <span className="material-symbols-outlined text-lg">send</span>
              </button>
            </div>
          </div>
        </aside>
      ) : (
        <button
          onClick={() => setChatOpen(true)}
          title="Faites évoluer vos indicateurs en le demandant"
          className="absolute bottom-5 right-5 z-30 pl-4 pr-5 py-3 rounded-full bg-primary text-white text-sm font-bold flex items-center gap-2 shadow-lg shadow-primary/30 hover:brightness-110 hover:-translate-y-0.5 transition-transform"
        >
          <span className="material-symbols-outlined text-lg">auto_awesome</span>
          Affiner
          {/* Ce qui a deja ete demande n'est pas perdu quand on replie. */}
          {messages.length > 0 && (
            <span className="ml-0.5 min-w-5 h-5 px-1.5 rounded-full bg-white/25 text-[11px] flex items-center justify-center tabular-nums">
              {messages.filter((m) => m.role === "user").length}
            </span>
          )}
        </button>
      )}
    </div>
  );
}
