/**
 * Le parcours en cinq étapes.
 *
 * Les étapes non livrées sont affichées mais désactivées, avec le sprint attendu.
 * Les masquer laisserait croire que le produit s'arrête là ; les faire cliquer sur
 * une maquette vide serait pire.
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAtelier } from "@/lib/atelier";
import { ETAPES } from "@/lib/parcours";

export function Navigation() {
  const chemin = usePathname();
  const { espace, fichier } = useAtelier();

  return (
    <header
      className="sticky top-0 z-20 border-b backdrop-blur"
      style={{
        borderColor: "var(--bordure)",
        background: "color-mix(in oklab, var(--plan) 88%, transparent)",
      }}
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
        <Link href="/" className="text-sm font-semibold tracking-tight">
          MegLabs
        </Link>

        <nav className="flex flex-wrap items-center gap-1">
          {ETAPES.map((etape, rang) => {
            const actif = chemin === etape.chemin;
            const contenu = (
              <span className="flex items-baseline gap-1.5">
                <span
                  className="chiffres-alignes text-[11px]"
                  style={{ color: "var(--ink-muted)" }}
                >
                  {rang + 1}
                </span>
                {etape.titre}
              </span>
            );

            if (!etape.disponible) {
              return (
                <span
                  key={etape.chemin}
                  title={`Disponible au ${etape.attendu} — ${etape.resume}`}
                  className="cursor-not-allowed rounded-lg px-2.5 py-1.5 text-sm"
                  style={{ color: "var(--ink-muted)" }}
                >
                  {contenu}
                </span>
              );
            }

            return (
              <Link
                key={etape.chemin}
                href={etape.chemin}
                title={etape.resume}
                aria-current={actif ? "page" : undefined}
                className="rounded-lg px-2.5 py-1.5 text-sm transition-colors"
                style={{
                  background: actif ? "var(--surface-1)" : "transparent",
                  color: actif ? "var(--ink-1)" : "var(--ink-2)",
                  boxShadow: actif ? "inset 0 0 0 1px var(--bordure)" : undefined,
                }}
              >
                {contenu}
              </Link>
            );
          })}
        </nav>

        {espace && (
          <div
            className="ml-auto flex min-w-0 items-baseline gap-2 text-xs"
            style={{ color: "var(--ink-2)" }}
          >
            <span className="truncate">{espace.nom}</span>
            {fichier && (
              <>
                <span aria-hidden style={{ color: "var(--ink-muted)" }}>
                  ·
                </span>
                <span className="truncate font-medium">{fichier.nom}</span>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
