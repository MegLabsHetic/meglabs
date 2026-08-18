import Link from "next/link";

import { Logo3D } from "@/components/Logo3D";
import { Revele } from "@/components/Revele";
import { ETAPES } from "@/lib/parcours";

/**
 * Les chiffres ci-dessous sont MESURÉS sur le jeu de démonstration, pas estimés.
 * Chacun est reproductible : c'est ce qui les rend défendables devant un jury.
 * Ils doivent être revérifiés si le générateur de données ou le routage changent.
 */
const PREUVES = [
  {
    valeur: "8 / 8",
    titre: "anomalies retrouvées",
    detail:
      "Le générateur injecte huit salaires aberrants. Le profileur les retrouve tous, sans rien savoir de lui.",
  },
  {
    valeur: "5 494",
    titre: "caractères transmis au modèle",
    detail:
      "Contre 36 475 octets de fichier. Seuls des noms de colonnes, trois exemples et des agrégats sortent d'ici.",
  },
  {
    valeur: "0,017 ¢",
    titre: "le coût d'une question",
    detail:
      "Mesuré sur une vraie génération SQL, affiché en direct. Chaque appel est compté, aucun n'est estimé.",
  },
  {
    valeur: "−65 %",
    titre: "de jetons en moins",
    detail:
      "À réponse identique, en ajustant la profondeur de raisonnement. L'optimisation du coût est aussi celle de l'empreinte.",
  },
];

const PILIERS = [
  {
    titre: "Souveraineté",
    phrase: "Aucune donnée personnelle n'atteint jamais le modèle.",
    detail:
      "La détection des adresses, téléphones, IBAN et numéros de sécurité sociale se fait en Python, sur ce serveur. Un service qui enverrait vos colonnes à un modèle pour lui demander si elles sont sensibles aurait déjà divulgué ce qu'il protège.",
  },
  {
    titre: "Transparence",
    phrase: "Vous voyez tout ce qui se passe, et vous pouvez tout annuler.",
    detail:
      "Le SQL généré est affiché. Chaque transformation est tracée et réversible. La session s'exporte en notebook Python — les outils sans code enferment, celui-ci rend le code.",
  },
  {
    titre: "Proactivité",
    phrase: "La plateforme pose les questions avant vous.",
    detail:
      "Elle repère les valeurs aberrantes, les corrélations, les formats incohérents, et propose les questions qui en découlent. C'est la réponse au vrai problème du non-technicien : la page blanche.",
  },
  {
    titre: "Accessibilité",
    phrase: "Le français est la seule compétence requise.",
    detail:
      "Pas de SQL, pas de syntaxe, pas de jargon dans l'interface. Une question posée comme on la poserait à un collègue, une réponse écrite comme un collègue l'écrirait.",
  },
  {
    titre: "Frugalité",
    phrase: "Chaque analyse affiche ce qu'elle coûte, et on minimise ce coût.",
    detail:
      "Le bon modèle pour la bonne tâche, du Python pur quand un modèle n'apporte rien, du calcul local plutôt qu'une infrastructure permanente. Le compteur est à l'écran, pas dans une note de bas de page.",
  },
];

export default function Accueil() {
  return (
    <main>
      {/* --- Hero ------------------------------------------------------- */}
      <section className="mx-auto max-w-4xl px-6 pb-24 pt-20 text-center sm:pt-28">
        <div className="apparait flex flex-col items-center">
          <Logo3D taille={132} />

          <p
            className="mt-8 text-xs uppercase tracking-[0.18em]"
            style={{ color: "var(--accent)" }}
          >
            Analyse de données en français
          </p>

          <h1 className="titre-serre mt-4 text-5xl font-semibold sm:text-6xl">
            Posez la question.
            <br />
            <span style={{ color: "var(--ink-3)" }}>On s&apos;occupe du reste.</span>
          </h1>

          <p
            className="mx-auto mt-6 max-w-xl text-lg leading-relaxed"
            style={{ color: "var(--ink-2)" }}
          >
            Chargez vos fichiers, écrivez ce que vous cherchez comme vous le diriez à un
            collègue. Vous obtenez l&apos;analyse, les graphiques, les prédictions et le
            rapport — sans une ligne de code.
          </p>

          {/* Un champ qui a la forme de ce qui arrive au sprint 2, mais qui mène à ce
              qui fonctionne aujourd'hui : il ne fait pas semblant de répondre. */}
          <Link
            href="/donnees"
            className="group mt-10 flex w-full max-w-xl items-center gap-3 rounded-full border px-5 py-4 text-left transition-colors"
            style={{ background: "var(--panneau)", borderColor: "var(--filet-fort)" }}
          >
            <span aria-hidden style={{ color: "var(--accent)" }}>
              ⌕
            </span>
            <span className="flex-1 truncate" style={{ color: "var(--ink-3)" }}>
              Quel est le salaire moyen par service ?
            </span>
            <span
              className="shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-transform group-hover:translate-x-0.5"
              style={{ background: "var(--accent)", color: "#04110f" }}
            >
              Commencer
            </span>
          </Link>

          <p className="mt-4 text-sm" style={{ color: "var(--ink-muted)" }}>
            Vos fichiers restent sur votre serveur. Rien n&apos;est envoyé ailleurs sans que
            vous le voyiez.
          </p>
        </div>
      </section>

      {/* --- Preuves ---------------------------------------------------- */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Revele>
          <h2 className="titre-serre text-3xl font-semibold">
            Des chiffres, pas des promesses
          </h2>
          <p className="mt-3 max-w-2xl" style={{ color: "var(--ink-2)" }}>
            Chacune de ces valeurs est mesurée sur le jeu de démonstration et rejouable.
            Aucune n&apos;est une estimation.
          </p>
        </Revele>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {PREUVES.map((preuve, rang) => (
            <Revele key={preuve.titre} delai={rang * 70}>
              <article className="panneau-doux h-full p-6">
                <p
                  className="text-4xl font-semibold tracking-tight"
                  style={{ color: "var(--accent)" }}
                >
                  {preuve.valeur}
                </p>
                <h3 className="mt-2 font-medium">{preuve.titre}</h3>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--ink-3)" }}>
                  {preuve.detail}
                </p>
              </article>
            </Revele>
          ))}
        </div>
      </section>

      {/* --- Parcours --------------------------------------------------- */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Revele>
          <h2 className="titre-serre text-3xl font-semibold">Cinq étapes, dans cet ordre</h2>
          <p className="mt-3 max-w-2xl" style={{ color: "var(--ink-2)" }}>
            C&apos;est l&apos;ordre du travail réel : on ne pose pas de question à des données
            qu&apos;on n&apos;a pas encore regardées.
          </p>
        </Revele>

        <ol className="mt-10 space-y-3">
          {ETAPES.map((etape, rang) => (
            <Revele key={etape.chemin} delai={rang * 60}>
              <li className="panneau flex flex-wrap items-baseline gap-x-5 gap-y-1 p-5">
                <span
                  className="chiffres-alignes text-sm tabular-nums"
                  style={{ color: "var(--accent)" }}
                >
                  {String(rang + 1).padStart(2, "0")}
                </span>
                <h3 className="text-lg font-medium">{etape.titre}</h3>
                <p className="w-full sm:w-auto sm:flex-1" style={{ color: "var(--ink-3)" }}>
                  {etape.resume}
                </p>
                <span
                  className="text-xs"
                  style={{ color: etape.disponible ? "var(--etat-bon)" : "var(--ink-muted)" }}
                >
                  {etape.disponible ? "● disponible" : `○ ${etape.attendu}`}
                </span>
              </li>
            </Revele>
          ))}
        </ol>
      </section>

      {/* --- Piliers ---------------------------------------------------- */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Revele>
          <h2 className="titre-serre text-3xl font-semibold">Ce qui nous distingue</h2>
          <p className="mt-3 max-w-2xl" style={{ color: "var(--ink-2)" }}>
            Cinq idées. Chaque décision technique doit en servir au moins une, sinon elle
            n&apos;entre pas dans le produit.
          </p>
        </Revele>

        <div className="mt-10 space-y-3">
          {PILIERS.map((pilier, rang) => (
            <Revele key={pilier.titre} delai={rang * 55}>
              <article className="panneau grid gap-3 p-6 md:grid-cols-[200px_1fr] md:gap-8">
                <div>
                  <h3 className="text-lg font-medium">{pilier.titre}</h3>
                  <p className="mt-1 text-sm" style={{ color: "var(--accent)" }}>
                    {pilier.phrase}
                  </p>
                </div>
                <p className="leading-relaxed" style={{ color: "var(--ink-3)" }}>
                  {pilier.detail}
                </p>
              </article>
            </Revele>
          ))}
        </div>
      </section>

      {/* --- Appel final ------------------------------------------------ */}
      <section className="mx-auto max-w-3xl px-6 pb-28 pt-10 text-center">
        <Revele>
          <h2 className="titre-serre text-4xl font-semibold">
            Commencez par un fichier
          </h2>
          <p className="mx-auto mt-4 max-w-xl" style={{ color: "var(--ink-2)" }}>
            Déposez un CSV ou un Excel. En quelques secondes, vous savez ce qu&apos;il
            contient, ce qui cloche dedans, et ce qui doit être protégé.
          </p>
          <Link
            href="/donnees"
            className="mt-8 inline-block rounded-full px-7 py-3.5 font-medium transition-transform hover:-translate-y-0.5"
            style={{ background: "var(--accent)", color: "#04110f", boxShadow: "var(--lueur)" }}
          >
            Déposer un fichier
          </Link>
        </Revele>
      </section>
    </main>
  );
}
