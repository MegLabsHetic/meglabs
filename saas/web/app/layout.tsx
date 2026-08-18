import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DataVox — Vos données répondent en français",
  description:
    "Déposez un fichier, posez vos questions, obtenez le chiffre, le graphique et la requête qui l'a produit. Tableaux de bord vivants et rapports prêts à envoyer.",
  // Icone vectorielle : nette a toutes les tailles, un seul fichier.
  icons: { icon: [{ url: "/favicon.svg", type: "image/svg+xml" }] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // La classe `dark` n'est plus figée : elle est posée par le script
    // ci-dessous, avant le premier rendu.
    <html lang="fr" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 font-display antialiased">
        {/*
          Thème appliqué AVANT le premier rendu. Sans ce script, une page en
          mode clair afficherait un éclair sombre au chargement, le temps que
          React s'exécute — c'est le défaut le plus visible d'un thème géré
          uniquement côté composant.
        */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('datavox.theme')||'system';var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);}catch(e){document.documentElement.classList.add('dark');}})();`,
          }}
        />
        {/* Sans JavaScript, les blocs a apparition resteraient invisibles :
            on annule leur etat initial plutot que de servir une page vide. */}
        <noscript>
          <style>{`.lp-reveal { opacity: 1 !important; transform: none !important; }`}</style>
        </noscript>
        {children}
      </body>
    </html>
  );
}
