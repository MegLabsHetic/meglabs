"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiPublic } from "@/lib/api";
import { ouvrirSession } from "@/lib/session";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";

/**
 * Connexion et inscription.
 *
 * Les comptes sont geres par notre propre api : aucun service tiers n'est
 * requis. Le mot de passe part en HTTPS, n'est jamais conserve cote client,
 * et le serveur n'en garde qu'une empreinte Argon2id.
 */

const MIN_MOT_DE_PASSE = 8;

function Formulaire() {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<"connexion" | "inscription">("connexion");
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [nom, setNom] = useState("");
  const [visible, setVisible] = useState(false);
  const [erreur, setErreur] = useState("");
  const [occupe, setOccupe] = useState(false);

  const expiree = params.get("expiree") === "1";
  const trop_court =
    mode === "inscription" && motDePasse.length > 0 && motDePasse.length < MIN_MOT_DE_PASSE;

  async function envoyer(e: React.FormEvent) {
    e.preventDefault();
    if (occupe || trop_court) return;
    setOccupe(true);
    setErreur("");
    try {
      const chemin = mode === "connexion" ? "/v1/auth/login" : "/v1/auth/register";
      const corps =
        mode === "connexion"
          ? { email, password: motDePasse }
          : { email, password: motDePasse, name: nom };
      const res = await apiPublic<any>(chemin, corps);
      ouvrirSession(res.token, res.user);
      router.push("/dashboard");
    } catch (err: any) {
      // Le serveur renvoie volontairement le meme refus pour un e-mail
      // inconnu et un mot de passe faux : on ne cherche pas a le detailler.
      setErreur(
        err.message === "unauthorized"
          ? "E-mail ou mot de passe incorrect."
          : err.message || "Échec de la connexion"
      );
    } finally {
      setOccupe(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 bg-background-light dark:bg-[#080b14]">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <Link href="/" aria-label="DataVox — accueil">
            <Logo size={38} id="dv-login" />
          </Link>
          <ThemeToggle compact />
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 shadow-xl">
          <h1 className="text-2xl font-bold text-center">
            {mode === "connexion" ? "Bon retour" : "Créer un compte"}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm text-center mt-1 mb-6">
            {mode === "connexion"
              ? "Connectez-vous pour retrouver vos projets"
              : "Quelques secondes suffisent"}
          </p>

          {expiree && (
            <p className="mb-4 text-sm text-amber-600 dark:text-amber-500 bg-amber-500/10 rounded-lg px-3 py-2">
              Votre session a expiré. Reconnectez-vous.
            </p>
          )}

          <form onSubmit={envoyer} className="space-y-4">
            {mode === "inscription" && (
              <label className="block">
                <span className="text-sm font-medium">Nom</span>
                <input
                  value={nom}
                  onChange={(e) => setNom(e.target.value)}
                  autoComplete="name"
                  placeholder="Facultatif"
                  className="mt-1.5 w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary/30"
                />
              </label>
            )}

            <label className="block">
              <span className="text-sm font-medium">E-mail</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                placeholder="vous@exemple.fr"
                className="mt-1.5 w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary/30"
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium">Mot de passe</span>
              <div className="relative mt-1.5">
                <input
                  type={visible ? "text" : "password"}
                  required
                  value={motDePasse}
                  onChange={(e) => setMotDePasse(e.target.value)}
                  autoComplete={mode === "connexion" ? "current-password" : "new-password"}
                  minLength={mode === "inscription" ? MIN_MOT_DE_PASSE : undefined}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 pr-11 text-sm focus:ring-2 focus:ring-primary/30"
                />
                <button
                  type="button"
                  onClick={() => setVisible((v) => !v)}
                  aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                  className="absolute right-1 top-1/2 -translate-y-1/2 w-9 h-9 rounded-md flex items-center justify-center text-slate-400 hover:text-primary"
                >
                  <span className="material-symbols-outlined text-lg">
                    {visible ? "visibility_off" : "visibility"}
                  </span>
                </button>
              </div>
              {mode === "inscription" && (
                <span
                  className={`block mt-1.5 text-xs ${
                    trop_court ? "text-amber-600 dark:text-amber-500" : "text-slate-500"
                  }`}
                >
                  {MIN_MOT_DE_PASSE} caractères minimum
                </span>
              )}
            </label>

            {erreur && (
              <p className="text-sm text-red-500 bg-red-500/10 rounded-lg px-3 py-2">{erreur}</p>
            )}

            <button
              type="submit"
              disabled={occupe || trop_court}
              className="w-full bg-primary text-white rounded-lg py-2.5 font-bold hover:brightness-110 transition disabled:opacity-50 inline-flex items-center justify-center gap-2"
            >
              {occupe ? (
                <>
                  <span className="spinner" />
                  {mode === "connexion" ? "Connexion…" : "Création…"}
                </>
              ) : mode === "connexion" ? (
                "Se connecter"
              ) : (
                "Créer mon compte"
              )}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 dark:text-slate-400 mt-6">
            {mode === "connexion" ? "Pas encore de compte ?" : "Vous avez déjà un compte ?"}{" "}
            <button
              onClick={() => {
                setMode(mode === "connexion" ? "inscription" : "connexion");
                setErreur("");
              }}
              className="text-primary font-semibold hover:underline"
            >
              {mode === "connexion" ? "Créer un compte" : "Se connecter"}
            </button>
          </p>
        </div>

        <p className="text-center text-xs text-slate-500 mt-6">
          Vos données restent dans votre entrepôt. Elles ne servent à entraîner aucun modèle.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  // useSearchParams impose une frontiere de suspense au rendu statique.
  return (
    <Suspense fallback={<div className="min-h-screen bg-background-light dark:bg-[#080b14]" />}>
      <Formulaire />
    </Suspense>
  );
}
