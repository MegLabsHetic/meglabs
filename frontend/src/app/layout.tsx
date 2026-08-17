import type { Metadata } from "next";

import { Navigation } from "@/components/Navigation";
import { FournisseurAtelier } from "@/lib/atelier";

import "./globals.css";

export const metadata: Metadata = {
  title: "MegLabs",
  description: "Analyse de données pilotée en français naturel.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>
        <FournisseurAtelier>
          <Navigation />
          {children}
        </FournisseurAtelier>
      </body>
    </html>
  );
}
