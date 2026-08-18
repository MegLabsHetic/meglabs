/**
 * Le parcours en cinq étapes, présenté comme une progression et non comme un menu.
 *
 * Les étapes non livrées restent visibles mais désactivées, avec le sprint attendu.
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
      className="sticky top-0 z-30 border-b backdrop-blur-xl"
      style={{
        borderColor: "var(--filet)",
        background: "color-mix(in oklab, var(--fond) 78%, transparent)",
      }}
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-2.5 w-2.5 rounded-full"
            style={{
              background: "linear-gradient(135deg, var(--deco-a), var(--deco-b))",
              boxShadow: "0 0 12px var(--deco-a)",
            }}
          />
          <span className="text-sm font-semibold tracking-tight">MegLabs</span>
        </Link>

        <nav className="flex flex-wrap items-center gap-0.5">
          {ETAPES.map((etape, rang) => {
            const actif = chemin === etape.chemin;

            const numero = (
              <span
                className="chiffres-alignes text-[10px] tabular-nums"
                style={{ color: actif ? "var(--accent)" : "var(--ink-muted)" }}
              >
                {String(rang + 1).padStart(2, "0")}
              </span>
            );

            if (!etape.disponible) {
              return (
                <span
                  key={etape.chemin}
                  title={`Disponible au ${etape.attendu} — ${etape.resume}`}
                  className="flex cursor-not-allowed items-baseline gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
                  style={{ color: "var(--ink-muted)" }}
                >
                  {numero}
                  {etape.titre}
                </span>
              );
            }

            return (
              <Link
                key={etape.chemin}
                href={etape.chemin}
                title={etape.resume}
                aria-current={actif ? "page" : undefined}
                className="relative flex items-baseline gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition-colors"
                style={{
                  color: actif ? "var(--ink-1)" : "var(--ink-3)",
                  background: actif ? "var(--voile)" : "transparent",
                }}
              >
                {numero}
                {etape.titre}
                {actif && (
                  <span
                    aria-hidden
                    className="absolute inset-x-2.5 -bottom-[13px] h-px"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent, var(--accent), transparent)",
                      boxShadow: "0 0 10px var(--accent)",
                    }}
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {espace && (
          <div
            className="ml-auto flex min-w-0 items-center gap-2 text-xs"
            style={{ color: "var(--ink-3)" }}
          >
            <span
              aria-hidden
              className="h-1.5 w-1.5 shrink-0 rounded-full pulse"
              style={{ background: "var(--etat-bon)", boxShadow: "0 0 8px var(--etat-bon)" }}
            />
            <span className="max-w-[160px] truncate">{espace.nom}</span>
            {fichier && (
              <>
                <span aria-hidden style={{ color: "var(--filet-fort)" }}>
                  /
                </span>
                <span className="max-w-[200px] truncate font-medium" style={{ color: "var(--ink-2)" }}>
                  {fichier.nom}
                </span>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
