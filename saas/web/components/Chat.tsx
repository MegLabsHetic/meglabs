"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import SqlChart from "@/components/SqlChart";
import ReportButton from "@/components/ReportButton";

const PRIMARY = "#0d59f2";

/**
 * Le graphique d'une réponse passe par le même composant que le tableau de
 * bord : même palette, même vue tableau, mêmes règles de forme. La requête
 * SQL exécutée reste consultable — l'analyse doit rester auditable.
 */
function InlineViz({ v, onPin }: { v: any; onPin?: (v: any) => void }) {
  if (!v) return null;
  return (
    <div className="mt-4">
      <SqlChart
        title={v.titre}
        result={v.lignes ? { columns: v.colonnes || [], rows: v.lignes } : null}
        viz={v.viz}
        format={v.format}
        erreur={v.erreur}
        sql={v.sql}
        actions={
          onPin && !v.erreur ? (
            <button
              onClick={() => onPin(v)}
              title="Épingler au tableau de bord"
              aria-label="Épingler au tableau de bord"
              className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <span className="material-symbols-outlined text-base">push_pin</span>
            </button>
          ) : undefined
        }
      />
    </div>
  );
}

export default function Chat({
  projectId,
  schema,
  onPin,
}: {
  projectId: string;
  schema: any;
  onPin?: (v: any) => void;
}) {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
  }, [projectId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Les amorces sont tirées du schéma réel de l'entrepôt : une question
  // proposée porte toujours sur une colonne qui existe.
  const table = schema?.tables?.[0];
  const cols: any[] = table?.columns || [];
  const textCol = cols.find((c) => c.type === "VARCHAR");
  const dateCol = cols.find((c) => String(c.type).startsWith("TIMESTAMP") || c.type === "DATE");
  const starters = [
    "Donne-moi un résumé de mes données",
    textCol && `Montre la répartition par ${textCol.name}`,
    dateCol && "Quelle est l'évolution dans le temps ?",
  ].filter(Boolean) as string[];

  async function send(text: string) {
    const msg = text.trim();
    if (!msg || loading) return;
    setInput("");
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    // La demande d'origine accompagne le rapport : « insiste sur les annulations »
    // doit se retrouver dans le document.
    const demande = msg;
    setLoading(true);
    try {
      const res = await apiFetch<any>(`/v1/projects/${projectId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message: msg, history }),
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reponse || "",
          visualisation: res.visualisation,
          suggestions: res.suggestions || [],
          action: res.action || null,
          demande,
        },
      ]);
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: "assistant", content: "⚠️ " + e.message }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto text-center mt-10">
            <div className="w-14 h-14 rounded-2xl bg-primary/15 text-primary flex items-center justify-center mx-auto mb-4">
              <span className="material-symbols-outlined text-3xl">smart_toy</span>
            </div>
            <h3 className="text-xl font-bold">Posez vos questions en langage naturel</h3>
            <p className="text-slate-500 dark:text-slate-400 mt-2">
              L&apos;assistant analyse vos données, répond, et génère les graphiques pour vous.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              {starters.map((s) => (
                <button key={s} onClick={() => send(s)}
                  className="px-4 py-2 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-sm font-medium hover:border-primary transition-colors">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex items-start gap-3 max-w-3xl ml-auto flex-row-reverse">
              <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-white text-xl">person</span>
              </div>
              <div className="bg-primary text-white px-4 py-3 rounded-2xl rounded-tr-none shadow">
                <p dir="auto" className="text-sm font-medium">{m.content}</p>
              </div>
            </div>
          ) : (
            <div key={i} className="flex items-start gap-3 max-w-4xl">
              <div className="w-9 h-9 rounded-lg bg-slate-200 dark:bg-slate-800 flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-primary text-xl">smart_toy</span>
              </div>
              <div className="flex-1 space-y-4">
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-5 py-4 rounded-2xl rounded-tl-none shadow-sm">
                  <p dir="auto" className="text-slate-700 dark:text-slate-200 leading-relaxed text-sm whitespace-pre-line">{m.content}</p>
                  <InlineViz v={m.visualisation} onPin={onPin} />
                  {m.action === "rapport" && (
                    <div className="mt-4">
                      <ReportButton projectId={projectId} demande={m.demande || ""} />
                    </div>
                  )}
                </div>
                {m.suggestions && m.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {m.suggestions.map((s: string) => (
                      <button key={s} onClick={() => send(s)}
                        className="px-3.5 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full text-xs font-semibold hover:border-primary transition-colors flex items-center gap-1.5 group">
                        {s}
                        <span className="material-symbols-outlined text-xs text-slate-400 group-hover:text-primary">arrow_forward</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        )}

        {loading && (
          <div className="flex items-center gap-3 max-w-4xl">
            <div className="w-9 h-9 rounded-lg bg-slate-200 dark:bg-slate-800 flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-primary text-xl">smart_toy</span>
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-5 py-4 rounded-2xl rounded-tl-none text-slate-400 text-sm">
              <span className="spinner" style={{ borderColor: "rgba(100,116,139,0.4)", borderTopColor: PRIMARY }} />
              L&apos;assistant réfléchit…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-background-dark/60 backdrop-blur">
        <div className="max-w-4xl mx-auto flex items-end gap-3 p-2 pl-4 bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700">
          <textarea
            className="flex-1 py-2.5 text-sm bg-transparent border-none focus:ring-0 resize-none max-h-32 outline-none"
            placeholder="Posez une question ou demandez un graphique…"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          <button onClick={() => send(input)} disabled={loading || !input.trim()}
            className="w-10 h-10 bg-primary text-white rounded-xl flex items-center justify-center hover:brightness-110 disabled:opacity-40 transition shrink-0">
            <span className="material-symbols-outlined">send</span>
          </button>
        </div>
        <p className="text-center text-[10px] text-slate-400 mt-3">
          Chaque réponse affiche la requête utilisée — les chiffres sont calculés sur vos données réelles.
        </p>
      </div>
    </div>
  );
}
