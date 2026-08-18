import Link from "next/link";
import HeroMockup from "@/components/landing/HeroMockup";
import Reveal from "@/components/landing/Reveal";
import Logo, { LogoMark } from "@/components/Logo";

/**
 * Page d'accueil.
 *
 * Argument central : la plupart des outils d'analyse conversationnels
 * *racontent* un chiffre. DataVox le *calcule*, et montre la requête. C'est
 * ce que la page doit faire comprendre en dix secondes — d'où la maquette
 * qui affiche la requête, et pas seulement le joli graphique.
 */

const ETAPES = [
  {
    n: "01",
    icone: "upload_file",
    titre: "Déposez votre fichier",
    texte:
      "Un CSV, un export de votre outil de gestion. Séparateur, encodage, colonnes mal nommées, dates en texte : tout est reconnu et remis d'aplomb automatiquement.",
    detail: "Aucune préparation de votre côté",
  },
  {
    n: "02",
    icone: "forum",
    titre: "Posez votre question en français",
    texte:
      "« Quel produit se vend le mieux en Espagne ? », « Le panier moyen progresse-t-il ? ». La réponse arrive avec le graphique, en quelques secondes.",
    detail: "Zéro formule, zéro tableau croisé",
  },
  {
    n: "03",
    icone: "dashboard",
    titre: "Gardez ce qui compte",
    texte:
      "Épinglez un graphique et il devient un indicateur suivi. Le mois suivant, vous redéposez votre fichier : tout le tableau de bord se met à jour seul.",
    detail: "Construit une fois, à jour toujours",
  },
];

const ATOUTS = [
  {
    icone: "function",
    titre: "Chaque chiffre est vérifiable",
    texte:
      "Sous chaque graphique, la requête exacte qui l'a produit. Vous pouvez la lire, la corriger, la donner à votre équipe technique. Rien n'est enfoui dans une boîte noire.",
  },
  {
    icone: "tune",
    titre: "Un tableau de bord qui s'écrit en parlant",
    texte:
      "« Ajoute le panier moyen par pays. » « Le chiffre d'affaires doit exclure les commandes annulées. » L'indicateur apparaît ou se recalcule immédiatement.",
  },
  {
    icone: "sync",
    titre: "Vos données changent, pas votre travail",
    texte:
      "Un nouvel export ? La structure est comparée à l'ancienne. Colonne renommée, colonnes réordonnées : c'est rattrapé. Fichier qui n'a rien à voir : on vous prévient au lieu de tout casser.",
  },
  {
    icone: "picture_as_pdf",
    titre: "Le rapport que vous auriez mis un après-midi à écrire",
    texte:
      "État des lieux, lecture des écarts, recommandations concrètes, graphiques inclus. Un PDF prêt à envoyer, demandé en une phrase.",
  },
  {
    icone: "workspaces",
    titre: "Un espace par sujet",
    texte:
      "Vos clients, vos équipes, vos filiales : chacun son espace, chacun ses projets, chacun ses tableaux de bord. Rien ne se mélange.",
  },
  {
    icone: "lock",
    titre: "Vos données restent les vôtres",
    texte:
      "Chaque projet dispose de son propre entrepôt isolé. Vos fichiers ne servent à entraîner aucun modèle, ni le nôtre ni celui de personne.",
  },
];

const AVANT_APRES = [
  { avant: "Exporter, nettoyer, retyper les colonnes", apres: "Déposer le fichier" },
  { avant: "Des heures de tableaux croisés", apres: "Une question en français" },
  { avant: "Un tableau de bord périmé dès le mois suivant", apres: "Une mise à jour en un dépôt" },
  { avant: "« D'où sort ce chiffre ? »", apres: "La requête est affichée sous le graphique" },
];

const FORMULATIONS = [
  "Quel est le panier moyen par pays ?",
  "Montre l'évolution mensuelle du chiffre d'affaires",
  "Quels produits sont en recul ce trimestre ?",
  "Quel est le taux de commandes annulées ?",
  "Compare l'Espagne et l'Italie",
  "Fais-moi un rapport complet en PDF",
  "Où perd-on le plus de marge ?",
  "Combien de commandes livrées en retard ?",
];

export default function Home() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-[#080b14] text-slate-100">
      {/* ── Navigation ─────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#080b14]/80 backdrop-blur-xl">
        <nav className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
          <Link href="/" aria-label="DataVox — accueil">
            <Logo size={30} />
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#fonctionnement" className="hover:text-white transition-colors">
              Fonctionnement
            </a>
            <a href="#atouts" className="hover:text-white transition-colors">
              Ce que ça change
            </a>
            <a href="#rapport" className="hover:text-white transition-colors">
              Rapports
            </a>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="hidden sm:block text-sm font-semibold text-slate-300 hover:text-white px-4 py-2 transition-colors"
            >
              Se connecter
            </Link>
            <Link
              href="/dashboard"
              className="bg-primary text-white rounded-lg px-4 py-2 text-sm font-bold hover:brightness-110 transition"
            >
              Essayer
            </Link>
          </div>
        </nav>
      </header>

      {/* ── Héros ──────────────────────────────── */}
      <section className="relative">
        {/* Grille et halos de fond */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage: "radial-gradient(70% 55% at 50% 0%, #000 30%, transparent 100%)",
            WebkitMaskImage: "radial-gradient(70% 55% at 50% 0%, #000 30%, transparent 100%)",
          }}
        />
        <div
          aria-hidden
          className="lp-drift pointer-events-none absolute -top-40 left-1/2 -z-10 h-[600px] w-[900px] -translate-x-1/2 opacity-60 blur-3xl"
          style={{
            background:
              "radial-gradient(45% 50% at 35% 40%, rgba(13,89,242,0.5), transparent 70%), radial-gradient(40% 45% at 70% 55%, rgba(124,58,237,0.35), transparent 70%)",
          }}
        />

        <div className="mx-auto max-w-6xl px-6 pt-16 pb-20 lg:pt-24 lg:pb-28 grid lg:grid-cols-2 gap-14 items-center">
          <div>
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-slate-300">
                <span className="size-1.5 rounded-full bg-[#1baf7a]" />
                Vos données répondent en français
              </span>
            </Reveal>

            <Reveal delay={80}>
              <h1 className="mt-6 text-[2.7rem] leading-[1.05] sm:text-6xl sm:leading-[1.02] font-black tracking-[-0.03em]">
                Arrêtez de fabriquer
                <br />
                des tableaux.
                <br />
                <span
                  className="lp-sheen"
                  style={{
                    backgroundImage:
                      "linear-gradient(100deg, #3987e5 0%, #8b7cf6 25%, #3987e5 50%, #8b7cf6 75%, #3987e5 100%)",
                  }}
                >
                  Posez la question.
                </span>
              </h1>
            </Reveal>

            <Reveal delay={160}>
              <p className="mt-6 text-lg text-slate-400 leading-relaxed max-w-xl">
                Déposez un fichier, demandez ce que vous voulez savoir. Vous obtenez le
                chiffre, le graphique, et <b className="text-slate-200">la requête qui l&apos;a
                produit</b> — pour que personne n&apos;ait à vous croire sur parole.
              </p>
            </Reveal>

            <Reveal delay={240}>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link
                  href="/dashboard"
                  className="group bg-primary text-white rounded-xl px-6 py-3.5 text-sm font-bold hover:brightness-110 transition inline-flex items-center gap-2 shadow-[0_12px_40px_-12px_rgba(13,89,242,0.9)]"
                >
                  Analyser mon premier fichier
                  <span className="material-symbols-outlined text-lg transition-transform group-hover:translate-x-0.5">
                    arrow_forward
                  </span>
                </Link>
                <Link
                  href="/dashboard"
                  className="lp-glow rounded-xl px-6 py-3.5 text-sm font-bold border border-white/12 text-slate-200 hover:text-white transition inline-flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-lg text-primary">bolt</span>
                  Voir la démo en 1 clic
                </Link>
              </div>
            </Reveal>

            <Reveal delay={320}>
              <p className="mt-5 text-xs text-slate-500">
                Sans carte bancaire · Un jeu de données d&apos;exemple vous attend
              </p>
            </Reveal>
          </div>

          <Reveal delay={200}>
            <HeroMockup />
          </Reveal>
        </div>
      </section>

      {/* ── Bandeau défilant de questions ───────── */}
      <section className="border-y border-white/[0.06] bg-white/[0.015] py-5 overflow-hidden">
        <div className="flex gap-3 w-max lp-marquee" aria-hidden>
          {[...FORMULATIONS, ...FORMULATIONS].map((q, i) => (
            <span
              key={i}
              className="shrink-0 rounded-full border border-white/[0.08] bg-white/[0.03] px-4 py-2 text-sm text-slate-400"
            >
              {q}
            </span>
          ))}
        </div>
        <p className="sr-only">
          Exemples de questions : {FORMULATIONS.join(", ")}.
        </p>
      </section>

      {/* ── Avant / après ──────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-center">
            Le travail que vous ne referez plus
          </h2>
        </Reveal>
        <Reveal delay={80}>
          <p className="mt-4 text-slate-400 text-center max-w-2xl mx-auto">
            Analyser, ce n&apos;est pas manipuler un tableur pendant trois heures. C&apos;est
            décider. Le reste devrait être automatique.
          </p>
        </Reveal>

        <div className="mt-12 grid sm:grid-cols-2 gap-4">
          {AVANT_APRES.map((l, i) => (
            <Reveal key={l.avant} delay={i * 70}>
              <div className="lp-tilt lp-glow h-full rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5">
                <p className="flex items-start gap-2.5 text-sm text-slate-500 line-through decoration-slate-600">
                  <span className="material-symbols-outlined text-base text-slate-600 shrink-0 no-underline">
                    close
                  </span>
                  {l.avant}
                </p>
                <p className="mt-3 flex items-start gap-2.5 text-sm font-semibold text-slate-100">
                  <span className="material-symbols-outlined text-base text-[#1baf7a] shrink-0">
                    check
                  </span>
                  {l.apres}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Fonctionnement ─────────────────────── */}
      <section id="fonctionnement" className="relative py-24">
        <div
          aria-hidden
          className="lp-drift pointer-events-none absolute inset-x-0 top-0 -z-10 h-[500px] opacity-40 blur-3xl"
          style={{
            background:
              "radial-gradient(40% 50% at 25% 40%, rgba(13,89,242,0.35), transparent 70%), radial-gradient(35% 45% at 75% 60%, rgba(124,58,237,0.25), transparent 70%)",
          }}
        />
        <div className="mx-auto max-w-6xl px-6">
          <Reveal>
            <p className="text-center text-xs font-bold uppercase tracking-[0.2em] text-primary">
              Trois étapes
            </p>
          </Reveal>
          <Reveal delay={60}>
            <h2 className="mt-3 text-3xl sm:text-4xl font-black tracking-tight text-center">
              De votre fichier à votre décision
            </h2>
          </Reveal>

          <div className="mt-14 grid md:grid-cols-3 gap-5">
            {ETAPES.map((e, i) => (
              <Reveal key={e.n} delay={i * 110}>
                <div className="lp-tilt lp-glow h-full rounded-2xl border border-white/[0.08] bg-gradient-to-b from-white/[0.05] to-transparent p-6">
                  <div className="flex items-center justify-between">
                    <span className="size-11 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center">
                      <span className="material-symbols-outlined text-primary">{e.icone}</span>
                    </span>
                    <span className="text-3xl font-black text-white/[0.08] tabular-nums">
                      {e.n}
                    </span>
                  </div>
                  <h3 className="mt-5 text-lg font-bold tracking-tight">{e.titre}</h3>
                  <p className="mt-2.5 text-sm text-slate-400 leading-relaxed">{e.texte}</p>
                  <p className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#1baf7a]">
                    <span className="material-symbols-outlined text-sm">check_circle</span>
                    {e.detail}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Preuve : la requête ────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <div className="grid lg:grid-cols-2 gap-14 items-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-[#1baf7a]/30 bg-[#1baf7a]/10 px-3 py-1.5 text-xs font-bold text-[#1baf7a]">
              <span className="material-symbols-outlined text-sm">verified</span>
              Aucun chiffre inventé
            </span>
            <h2 className="mt-6 text-3xl sm:text-4xl font-black tracking-tight leading-tight">
              Un assistant qui vous montre son travail
            </h2>
            <p className="mt-5 text-slate-400 leading-relaxed">
              Beaucoup d&apos;outils vous annoncent un résultat. Impossible de savoir d&apos;où
              il sort, ni s&apos;il est juste. Ici, la question est traduite en une requête —
              affichée sous chaque graphique — et ce sont vos données qui produisent le
              chiffre.
            </p>
            <ul className="mt-7 space-y-3.5">
              {[
                "La requête est lisible, modifiable et exportable",
                "Un calcul faux se voit, se corrige et ne se répète pas",
                "Votre équipe technique peut auditer n'importe quel indicateur",
              ].map((t) => (
                <li key={t} className="flex gap-3 text-sm text-slate-300">
                  <span className="material-symbols-outlined text-primary text-lg shrink-0">
                    check_circle
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={140}>
            <div className="lp-tilt rounded-2xl border border-white/[0.08] bg-[#0d1220] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-white/[0.08] flex items-center gap-2">
                <span className="material-symbols-outlined text-slate-500 text-base">code</span>
                <span className="text-xs font-semibold text-slate-400">
                  Requête de l&apos;indicateur « Panier moyen par pays »
                </span>
              </div>
              <pre className="p-5 text-[12px] leading-relaxed font-mono text-slate-300 overflow-x-auto">
                <span className="text-[#8b7cf6]">SELECT</span> pays{" "}
                <span className="text-[#8b7cf6]">AS</span> libelle,
                {"\n       "}
                <span className="text-[#3987e5]">AVG</span>(quantite * prix_unitaire){" "}
                <span className="text-[#8b7cf6]">AS</span> valeur
                {"\n"}
                <span className="text-[#8b7cf6]">FROM</span> ventes_2026
                {"\n"}
                <span className="text-[#8b7cf6]">WHERE</span> statut !={" "}
                <span className="text-[#1baf7a]">&apos;Annulé&apos;</span>
                {"\n"}
                <span className="text-[#8b7cf6]">GROUP BY</span> pays
                {"\n"}
                <span className="text-[#8b7cf6]">ORDER BY</span> valeur{" "}
                <span className="text-[#8b7cf6]">DESC</span>
              </pre>
              <div className="px-5 py-3 border-t border-white/[0.08] bg-white/[0.02] flex items-center gap-2">
                <span className="material-symbols-outlined text-[#1baf7a] text-base">
                  task_alt
                </span>
                <span className="text-xs text-slate-400">
                  Exécutée sur vos 250 lignes · 1 367 € au total
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Atouts ─────────────────────────────── */}
      <section id="atouts" className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-center">
            Ce que ça change concrètement
          </h2>
        </Reveal>

        <div className="mt-14 grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {ATOUTS.map((a, i) => (
            <Reveal key={a.titre} delay={(i % 3) * 90}>
              <div className="lp-tilt lp-glow h-full rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6">
                <span className="size-10 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center">
                  <span className="material-symbols-outlined text-primary">{a.icone}</span>
                </span>
                <h3 className="mt-5 font-bold tracking-tight">{a.titre}</h3>
                <p className="mt-2.5 text-sm text-slate-400 leading-relaxed">{a.texte}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Rapport ────────────────────────────── */}
      <section id="rapport" className="mx-auto max-w-6xl px-6 py-24">
        <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-br from-primary/[0.14] via-white/[0.02] to-transparent p-8 sm:p-12">
          <div
            aria-hidden
            className="lp-drift pointer-events-none absolute -right-24 -top-24 size-[420px] opacity-50 blur-3xl"
            style={{
              background: "radial-gradient(circle, rgba(13,89,242,0.5), transparent 70%)",
            }}
          />
          <div className="relative grid lg:grid-cols-2 gap-12 items-center">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-xs font-bold text-slate-200">
                <span className="material-symbols-outlined text-sm text-primary">
                  picture_as_pdf
                </span>
                Rapport complet
              </span>
              <h2 className="mt-6 text-3xl sm:text-4xl font-black tracking-tight leading-tight">
                « Fais-moi un rapport »
                <br />
                et il est écrit.
              </h2>
              <p className="mt-5 text-slate-400 leading-relaxed">
                Un document structuré : où vous en êtes, ce qui bouge et pourquoi, ce qu&apos;il
                faut faire ensuite. Avec vos graphiques. Prêt à envoyer à votre direction ou à
                votre client.
              </p>
              <div className="mt-7 flex flex-wrap gap-2">
                {["État des lieux chiffré", "Lecture des écarts", "Recommandations", "Graphiques inclus"].map(
                  (t) => (
                    <span
                      key={t}
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-slate-300"
                    >
                      {t}
                    </span>
                  )
                )}
              </div>
            </Reveal>

            <Reveal delay={140}>
              {/* Aperçu de document */}
              <div className="lp-float rounded-xl bg-white p-6 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.8)] rotate-[-1.2deg]">
                <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                  <div>
                    <p className="text-[13px] font-black tracking-tight text-slate-900">
                      Rapport d&apos;analyse — Ventes 2026
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      250 lignes · 9 indicateurs suivis
                    </p>
                  </div>
                  <span className="material-symbols-outlined text-primary">analytics</span>
                </div>

                <p className="mt-4 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  État des lieux
                </p>
                <div className="mt-2 space-y-1.5">
                  <div className="h-1.5 rounded bg-slate-200 w-full" />
                  <div className="h-1.5 rounded bg-slate-200 w-[92%]" />
                  <div className="h-1.5 rounded bg-slate-200 w-[70%]" />
                </div>

                <div className="mt-4 grid grid-cols-3 gap-2">
                  {[
                    { v: "75 221 €", l: "Chiffre d'affaires" },
                    { v: "250", l: "Commandes" },
                    { v: "14,4 %", l: "Annulations" },
                  ].map((k) => (
                    <div key={k.l} className="rounded-lg bg-slate-100 p-2">
                      <p className="text-[13px] font-black text-slate-900 tabular-nums">{k.v}</p>
                      <p className="text-[8px] text-slate-500 mt-0.5">{k.l}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-3 flex items-end gap-1.5 h-14 rounded-lg bg-slate-50 p-2">
                  {[62, 78, 45, 92, 70, 84].map((h, i) => (
                    <div
                      key={i}
                      className="lp-bar flex-1 rounded-t bg-[#2a78d6]"
                      style={{ height: `${h}%`, animationDelay: `${i * 90}ms` }}
                    />
                  ))}
                </div>

                <p className="mt-4 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Recommandations
                </p>
                <div className="mt-2 space-y-1.5">
                  {[
                    "Reprendre le suivi des commandes annulées en Espagne",
                    "Renforcer le stock Casque avant le pic de mars",
                  ].map((t) => (
                    <p key={t} className="flex gap-1.5 text-[9.5px] text-slate-700 leading-snug">
                      <span className="mt-[3px] size-1 shrink-0 rounded-full bg-[#1baf7a]" />
                      {t}
                    </p>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Appel final ────────────────────────── */}
      <section className="mx-auto max-w-3xl px-6 py-28 text-center">
        <Reveal>
          <h2 className="text-4xl sm:text-5xl font-black tracking-[-0.03em] leading-[1.05]">
            Votre prochain tableau de bord
            <br />
            <span
              className="lp-sheen"
              style={{
                backgroundImage:
                  "linear-gradient(100deg, #3987e5 0%, #8b7cf6 25%, #3987e5 50%, #8b7cf6 75%, #3987e5 100%)",
              }}
            >
              tient en une question.
            </span>
          </h2>
        </Reveal>
        <Reveal delay={90}>
          <p className="mt-6 text-slate-400 text-lg">
            Testez avec le jeu de données d&apos;exemple : vous verrez tout le produit en un
            clic, sans avoir à préparer un fichier.
          </p>
        </Reveal>
        <Reveal delay={170}>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Link
              href="/dashboard"
              className="group bg-primary text-white rounded-xl px-7 py-4 font-bold hover:brightness-110 transition inline-flex items-center gap-2 shadow-[0_12px_40px_-12px_rgba(13,89,242,0.9)]"
            >
              Commencer maintenant
              <span className="material-symbols-outlined transition-transform group-hover:translate-x-0.5">
                arrow_forward
              </span>
            </Link>
          </div>
        </Reveal>
      </section>

      {/* ── Pied de page ───────────────────────── */}
      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto max-w-6xl px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Logo size={28} tagline />
          <p className="text-xs text-slate-500">
            © {new Date().getFullYear()} DataVox · Vos données répondent en français
          </p>
        </div>
      </footer>
    </div>
  );
}
