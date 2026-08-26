/**
 * La conversation : poser une question en français, voir ce que la plateforme fait.
 *
 * Trois choses se passent en même temps à l'écran, et c'est voulu : la chaîne
 * d'agents s'allume, la réponse s'écrit mot à mot, et le coût monte. Chacune répond
 * à une question qu'un utilisateur se pose sans oser la formuler — que fait-il,
 * est-ce qu'il avance, et combien ça me coûte.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Alerte } from "@/components/Alerte";
import { DetailReponse } from "@/components/DetailReponse";
import { Graphique } from "@/components/Graphique";
import { EtapeAgent, TheatreAgents, integrer } from "@/components/TheatreAgents";
import { api } from "@/lib/api";
import { useAtelier } from "@/lib/atelier";
import { suggerer } from "@/lib/suggestions";
import type { AppelTrace, EvenementReparation, EvenementSql } from "@/lib/sse";
import type { Profil } from "@/lib/types";
import { poserQuestion } from "@/lib/sse";

/**
 * Toujours proposée en dernier : c'est la démonstration du refus. Le garde-fou
 * répond avec une alternative plutôt qu'une erreur, et personne ne penserait à
 * l'essayer sans y être invité.
 */
const REFUS = "Supprime toutes les lignes";

interface Tour {
  question: string;
  texte: string;
  etapes: EtapeAgent[];
  sql: EvenementSql | null;
  reparation: EvenementReparation | null;
  colonnes: string[];
  lignes: (string | number | null)[][];
  tronque: boolean;
  trace: AppelTrace[];
  cout: number;
  depuisCache: boolean;
  erreur: string | null;
  encours: boolean;
}

function tourVierge(question: string): Tour {
  return {
    question,
    texte: "",
    etapes: [],
    sql: null,
    reparation: null,
    colonnes: [],
    lignes: [],
    tronque: false,
    trace: [],
    cout: 0,
    depuisCache: false,
    erreur: null,
    encours: true,
  };
}

export default function Conversation() {
  const { espace, fichiers, fichier, chargement } = useAtelier();
  const [tours, setTours] = useState<Tour[]>([]);
  const [saisie, setSaisie] = useState("");
  const [occupe, setOccupe] = useState(false);
  const [profil, setProfil] = useState<Profil | null>(null);
  const bas = useRef<HTMLDivElement>(null);

  // Les suggestions parlent du fichier réellement chargé. Sans son profil on ne
  // propose que la démonstration du refus, plutôt que des exemples inventés qui
  // échoueraient sur des colonnes inexistantes.
  const cible = fichier ?? fichiers[0] ?? null;
  useEffect(() => {
    if (!cible) return;
    let vivant = true;
    api
      .profil(cible.id)
      .then((recu) => vivant && setProfil(recu))
      .catch(() => vivant && setProfil(null));
    return () => {
      vivant = false;
    };
  }, [cible]);

  const suggestions = [...(profil ? suggerer(profil) : []), REFUS];

  const cumul = tours.reduce((total, tour) => total + tour.cout, 0);
  const appels = tours.reduce((total, tour) => total + tour.trace.length, 0);
  const enCache = tours.filter((tour) => tour.depuisCache).length;

  /** Met à jour le dernier tour : c'est toujours celui qui reçoit les événements. */
  const majDernier = useCallback((transformer: (tour: Tour) => Tour) => {
    setTours((precedents) =>
      precedents.map((tour, rang) => (rang === precedents.length - 1 ? transformer(tour) : tour)),
    );
  }, []);

  const envoyer = useCallback(
    async (question: string) => {
      if (!espace || occupe || !question.trim()) return;
      setSaisie("");
      setOccupe(true);
      setTours((precedents) => [...precedents, tourVierge(question)]);

      await poserQuestion(espace.id, question, {
        agent: (evenement) =>
          majDernier((tour) => ({ ...tour, etapes: integrer(tour.etapes, evenement) })),
        jeton: (texte) => majDernier((tour) => ({ ...tour, texte: tour.texte + texte })),
        sql: (evenement) => majDernier((tour) => ({ ...tour, sql: evenement })),
        reparation: (evenement) => majDernier((tour) => ({ ...tour, reparation: evenement })),
        fin: (reponse) =>
          majDernier((tour) => ({
            ...tour,
            texte: reponse.texte,
            colonnes: reponse.colonnes,
            lignes: reponse.lignes,
            tronque: reponse.tronque,
            trace: reponse.trace,
            cout: reponse.cout_centimes,
            depuisCache: reponse.depuis_cache,
            encours: false,
          })),
        erreur: (message) =>
          majDernier((tour) => ({ ...tour, erreur: message, encours: false })),
      });

      setOccupe(false);
      bas.current?.scrollIntoView({ behavior: "smooth" });
    },
    [espace, occupe, majDernier],
  );

  if (chargement) return null;

  if (!espace || fichiers.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="titre-serre text-3xl">IA & prédictions</h1>
        <p className="mt-3" style={{ color: "var(--ink-2)" }}>
          Aucun fichier dans cet espace.{" "}
          <a href="/donnees" className="underline underline-offset-4">
            Déposez-en un
          </a>{" "}
          pour pouvoir poser des questions.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="titre-serre text-3xl">Posez votre question</h1>
          <p className="mt-1.5 text-sm" style={{ color: "var(--ink-2)" }}>
            En français, comme à un collègue. Vous verrez ce que fait chaque agent, la
            requête exécutée, et ce que la réponse a coûté.
          </p>
        </div>
        <div
          className="chiffres-alignes shrink-0 rounded-full border px-3 py-1.5 text-xs"
          style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
          title="Coût cumulé de la session, en centimes de dollar"
        >
          Session : {cumul.toFixed(3)} ¢ · {appels} appel{appels > 1 ? "s" : ""}
          {enCache > 0 && ` · ${enCache} en cache`}
        </div>
      </header>

      {tours.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => envoyer(suggestion)}
              className="rounded-full border px-3 py-1.5 text-sm transition-colors"
              style={{ borderColor: "var(--filet)", color: "var(--ink-2)" }}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* La marge basse laisse passer la barre de saisie, qui flotte au-dessus. */}
      <div className="flex flex-col gap-6 pb-24">
        {tours.map((tour, rang) => (
          <article key={rang} className="flex flex-col gap-3">
            <p className="text-sm font-medium">{tour.question}</p>

            <div className="panneau p-4">
              <TheatreAgents etapes={tour.etapes} />

              {tour.erreur ? (
                <div className={tour.etapes.length > 0 ? "mt-3" : ""}>
                  <Alerte message={tour.erreur} />
                </div>
              ) : (
                <>
                  {tour.texte && (
                    <p
                      className={`whitespace-pre-wrap leading-relaxed ${
                        tour.etapes.length > 0 ? "mt-3" : ""
                      }`}
                    >
                      {tour.texte}
                    </p>
                  )}
                  {tour.encours && !tour.texte && (
                    <p className="mt-3 text-sm" style={{ color: "var(--ink-muted)" }}>
                      …
                    </p>
                  )}
                  {tour.depuisCache && (
                    <p
                      className="mt-2 inline-block rounded-full px-2 py-0.5 text-xs"
                      style={{ background: "var(--accent-piste)", color: "var(--accent-clair)" }}
                    >
                      ⚡ réponse en cache — 0 centime
                    </p>
                  )}
                  <Graphique colonnes={tour.colonnes} lignes={tour.lignes} />
                  <DetailReponse
                    sql={tour.sql}
                    colonnes={tour.colonnes}
                    lignes={tour.lignes}
                    tronque={tour.tronque}
                    reparation={tour.reparation}
                    trace={tour.trace}
                  />
                </>
              )}
            </div>
          </article>
        ))}
        <div ref={bas} />
      </div>

      <form
        onSubmit={(evenement) => {
          evenement.preventDefault();
          void envoyer(saisie);
        }}
        className="sticky bottom-6 flex gap-2 rounded-xl border p-2 backdrop-blur-xl"
        style={{
          borderColor: "var(--filet)",
          background: "color-mix(in oklab, var(--panneau) 88%, transparent)",
        }}
      >
        <input
          value={saisie}
          onChange={(evenement) => setSaisie(evenement.target.value)}
          placeholder="Quel est le salaire moyen par service ?"
          disabled={occupe}
          className="flex-1 bg-transparent px-3 py-2 text-sm outline-none"
          style={{ color: "var(--ink-1)" }}
        />
        <button
          type="submit"
          disabled={occupe || !saisie.trim()}
          className="shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
          style={{ background: "var(--accent)", color: "#04110f" }}
        >
          {occupe ? "…" : "Demander"}
        </button>
      </form>
    </div>
  );
}
