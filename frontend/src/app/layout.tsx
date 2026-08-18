import type { Metadata, Viewport } from "next";

import { FondAnime } from "@/components/FondAnime";
import { Navigation } from "@/components/Navigation";
import { FournisseurAtelier } from "@/lib/atelier";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "MegLabs", template: "%s · MegLabs" },
  description:
    "Analyse de données pilotée en français naturel. Vos données restent chez vous.",
};

export const viewport: Viewport = {
  themeColor: "#070b16",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>
        <FondAnime />
        <FournisseurAtelier>
          <Navigation />
          {children}
          <footer
            className="mx-auto max-w-6xl px-6 pb-10 pt-16 text-xs"
            style={{ color: "var(--ink-muted)" }}
          >
            Vos fichiers restent sur ce serveur. Seuls des noms de colonnes, trois valeurs
            d&apos;exemple et des agrégats calculés localement peuvent atteindre un modèle de
            langage.
          </footer>
        </FournisseurAtelier>
      </body>
    </html>
  );
}
