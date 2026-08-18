"use client";

import { useEffect, useState } from "react";

/**
 * Bascule clair / sombre / système.
 *
 * Le thème est posé sur `<html>` par un script inséré AVANT le rendu (voir
 * layout.tsx) : sans cela, une page en mode clair afficherait un éclair
 * sombre au chargement, le temps que React s'exécute.
 *
 * La palette des graphiques suit automatiquement — `globals.css` définit ses
 * couleurs pour les deux modes, choisies et validées séparément, jamais
 * obtenues par inversion.
 */

export type Theme = "light" | "dark" | "system";

const CLE = "datavox.theme";

export function appliquerTheme(theme: Theme) {
  const sombre =
    theme === "dark" ||
    (theme === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", sombre);
}

const OPTIONS: Array<{ valeur: Theme; icone: string; libelle: string }> = [
  { valeur: "light", icone: "light_mode", libelle: "Clair" },
  { valeur: "dark", icone: "dark_mode", libelle: "Sombre" },
  { valeur: "system", icone: "computer", libelle: "Système" },
];

export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const enregistre = (window.localStorage.getItem(CLE) as Theme) || "system";
    setTheme(enregistre);

    // Suivre les changements du système tant que l'utilisateur n'a pas choisi.
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const suivre = () => {
      if ((window.localStorage.getItem(CLE) as Theme) === "system") {
        appliquerTheme("system");
      }
    };
    media.addEventListener("change", suivre);
    return () => media.removeEventListener("change", suivre);
  }, []);

  function choisir(valeur: Theme) {
    setTheme(valeur);
    window.localStorage.setItem(CLE, valeur);
    appliquerTheme(valeur);
  }

  if (compact) {
    // Un seul bouton qui alterne : pour les barres denses.
    const suivant: Theme = theme === "dark" ? "light" : "dark";
    return (
      <button
        onClick={() => choisir(suivant)}
        title={`Passer en mode ${suivant === "dark" ? "sombre" : "clair"}`}
        aria-label={`Passer en mode ${suivant === "dark" ? "sombre" : "clair"}`}
        className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        <span className="material-symbols-outlined text-base">
          {theme === "dark" ? "light_mode" : "dark_mode"}
        </span>
      </button>
    );
  }

  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 p-0.5"
      role="group"
      aria-label="Thème de l'interface"
    >
      {OPTIONS.map((o) => (
        <button
          key={o.valeur}
          onClick={() => choisir(o.valeur)}
          title={o.libelle}
          aria-label={o.libelle}
          aria-pressed={theme === o.valeur}
          className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors ${
            theme === o.valeur
              ? "bg-white dark:bg-slate-700 text-primary shadow-sm"
              : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          }`}
        >
          <span className="material-symbols-outlined text-base">{o.icone}</span>
        </button>
      ))}
    </div>
  );
}
