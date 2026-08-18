"use client";

import { useEffect, useState } from "react";

/**
 * Maquette vivante du produit : une question se tape toute seule, la requete
 * s'ecrit, le graphique se construit. C'est la demonstration du produit, pas
 * une illustration — les chiffres affiches sont ceux du jeu d'exemple.
 *
 * Aucune dependance : la sequence est un petit automate a etats, et tout
 * s'arrete si l'utilisateur a demande moins de mouvement.
 */

const QUESTION = "Quel est le chiffre d'affaires par pays ?";
const SQL = `SELECT pays, SUM(quantite * prix) AS ca
FROM ventes
WHERE statut = 'Livré'
GROUP BY pays
ORDER BY ca DESC`;

const BARS = [
  { pays: "Italie", valeur: 20788, pct: 100 },
  { pays: "Allemagne", valeur: 19104, pct: 92 },
  { pays: "Espagne", valeur: 17051, pct: 82 },
  { pays: "France", valeur: 15278, pct: 73 },
];

type Phase = "typing" | "thinking" | "sql" | "chart";

export default function HeroMockup() {
  const [typed, setTyped] = useState("");
  const [phase, setPhase] = useState<Phase>("typing");

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setTyped(QUESTION);
      setPhase("chart");
      return;
    }

    const timers: ReturnType<typeof setTimeout>[] = [];
    let i = 0;
    const type = () => {
      i += 1;
      setTyped(QUESTION.slice(0, i));
      if (i < QUESTION.length) {
        timers.push(setTimeout(type, 42));
      } else {
        timers.push(setTimeout(() => setPhase("thinking"), 420));
        timers.push(setTimeout(() => setPhase("sql"), 1250));
        timers.push(setTimeout(() => setPhase("chart"), 2500));
      }
    };
    timers.push(setTimeout(type, 700));
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="relative">
      {/* Halos derriere la maquette */}
      <div
        aria-hidden
        className="lp-drift absolute -inset-16 -z-10 opacity-70 blur-3xl"
        style={{
          background:
            "radial-gradient(38% 44% at 22% 28%, rgba(13,89,242,0.45), transparent 70%), radial-gradient(34% 40% at 80% 72%, rgba(120,80,240,0.35), transparent 70%)",
        }}
      />

      <div className="lp-float rounded-2xl border border-white/10 bg-[#0d1220]/90 shadow-[0_40px_120px_-30px_rgba(13,89,242,0.55)] backdrop-blur-xl overflow-hidden">
        {/* Barre de fenetre */}
        <div className="flex items-center gap-2 px-4 h-11 border-b border-white/10 bg-white/[0.03]">
          <span className="size-2.5 rounded-full bg-[#ff5f57]" />
          <span className="size-2.5 rounded-full bg-[#febc2e]" />
          <span className="size-2.5 rounded-full bg-[#28c840]" />
          <span className="ml-3 text-[11px] text-slate-400 font-medium">
            ventes_2026 · 250 lignes
          </span>
        </div>

        <div className="p-5 space-y-4">
          {/* Question */}
          <div className="flex justify-end">
            <div className="max-w-[85%] bg-primary text-white text-sm rounded-2xl rounded-tr-sm px-4 py-2.5 font-medium">
              {typed}
              {phase === "typing" && <span className="lp-caret ml-0.5">▍</span>}
            </div>
          </div>

          {/* Reponse */}
          {phase !== "typing" && (
            <div className="flex gap-3">
              <div className="size-8 shrink-0 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-lg">
                  insights
                </span>
              </div>

              <div className="flex-1 min-w-0 space-y-3">
                {phase === "thinking" ? (
                  <div className="flex gap-1.5 py-3">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="size-1.5 rounded-full bg-slate-500 lp-float"
                        style={{ animationDelay: `${i * 160}ms`, animationDuration: "1.2s" }}
                      />
                    ))}
                  </div>
                ) : (
                  <>
                    {/* La requete : c'est l'argument de vente, on la montre */}
                    <pre className="text-[10.5px] leading-relaxed font-mono text-slate-300 bg-black/40 border border-white/10 rounded-lg p-3 overflow-x-auto">
                      {SQL}
                    </pre>

                    {phase === "chart" && (
                      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                        <div className="flex items-baseline justify-between mb-3">
                          <p className="text-xs font-semibold text-slate-200">
                            Chiffre d&apos;affaires par pays
                          </p>
                          <p className="text-[11px] text-slate-400 tabular-nums">
                            Total 72 221 €
                          </p>
                        </div>

                        <div className="flex items-stretch gap-3 h-28">
                          {BARS.map((b, i) => (
                            <div
                              key={b.pays}
                              className="flex-1 h-full flex flex-col items-center gap-1.5"
                            >
                              {/* Etiquette directe : la valeur ne depend jamais
                                  de la seule couleur. */}
                              <span className="text-[10px] text-slate-400 tabular-nums">
                                {(b.valeur / 1000).toFixed(1).replace(".", ",")} k€
                              </span>
                              {/* Piste de hauteur definie : une hauteur en %
                                  ne se resout pas contre un parent auto. */}
                              <div className="flex-1 min-h-0 w-full flex items-end">
                                <div
                                  className="lp-bar w-full rounded-t bg-[#3987e5]"
                                  style={{
                                    height: `${b.pct}%`,
                                    animationDelay: `${i * 110}ms`,
                                  }}
                                />
                              </div>
                              <span className="text-[10px] text-slate-400">{b.pays}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Pastilles : sous la maquette, jamais par-dessus — elles masqueraient
          la requete, qui est justement ce qu'on veut montrer. */}
      <div className="mt-4 flex flex-wrap justify-center gap-2.5">
        <span
          className="lp-float flex items-center gap-2 rounded-xl border border-white/10 bg-[#0d1220]/95 px-3 py-2 shadow-xl backdrop-blur"
          style={{ animationDelay: "1.2s" }}
        >
          <span className="material-symbols-outlined text-[#1baf7a] text-base">verified</span>
          <span className="text-[11px] font-semibold text-slate-200">
            Chiffre calculé, pas rédigé
          </span>
        </span>
        <span
          className="lp-float flex items-center gap-2 rounded-xl border border-white/10 bg-[#0d1220]/95 px-3 py-2 shadow-xl backdrop-blur"
          style={{ animationDelay: "2.4s" }}
        >
          <span className="material-symbols-outlined text-primary text-base">bolt</span>
          <span className="text-[11px] font-semibold text-slate-200">Réponse en 4 secondes</span>
        </span>
      </div>
    </div>
  );
}
