"use client";

import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Schema de l'entrepot : les tables, leurs colonnes typees, et les liens
 * deduits entre elles.
 *
 * Disposition en etoile : la table qui porte le plus de liens est placee au
 * centre, les autres autour. C'est la forme naturelle d'un entrepot (une
 * table de faits, des dimensions autour) et elle evite les croisements de
 * traits qu'une grille produirait.
 *
 * Aucune librairie de graphe : les cartes sont positionnees en absolu et les
 * liens tires en SVG derriere elles.
 */

type Colonne = { name: string; type: string; label?: string; samples?: string[] };
type TableSchema = { name: string; rows: number; columns: Colonne[] };
type Relation = {
  source: string;
  colonne_source: string;
  cible: string;
  colonne_cible: string;
  couverture: number;
};

/** Type SQL ramene a une famille lisible, avec sa couleur de pastille. */
function famille(type: string): { court: string; classe: string } {
  const t = (type || "").toUpperCase();
  if (t.startsWith("TIMESTAMP") || t === "DATE" || t === "TIME")
    return { court: "date", classe: "bg-[#eda100]" };
  if (
    t.includes("INT") ||
    t.includes("DECIMAL") ||
    t.includes("DOUBLE") ||
    t.includes("FLOAT") ||
    t.includes("REAL")
  )
    return { court: "nombre", classe: "bg-[#1baf7a]" };
  if (t === "BOOLEAN") return { court: "booléen", classe: "bg-[#4a3aa7]" };
  return { court: "texte", classe: "bg-[#2a78d6]" };
}

const LARGEUR = 232;

function CarteTable({
  table,
  centrale,
  clefs,
}: {
  table: TableSchema;
  centrale: boolean;
  clefs: Set<string>;
}) {
  return (
    <div
      style={{ width: LARGEUR }}
      className={`rounded-xl border bg-white dark:bg-slate-900 shadow-sm overflow-hidden ${
        centrale
          ? "border-primary/50 ring-1 ring-primary/20"
          : "border-slate-200 dark:border-slate-800"
      }`}
    >
      <div
        className={`px-3 py-2 flex items-center gap-2 ${
          centrale ? "bg-primary/10" : "bg-slate-50 dark:bg-slate-800/60"
        }`}
      >
        <span className="material-symbols-outlined text-base text-primary">table_chart</span>
        <span className="text-sm font-bold truncate" title={table.name}>
          {table.name}
        </span>
        <span className="ml-auto text-[10px] text-slate-400 tabular-nums shrink-0">
          {table.rows.toLocaleString("fr-FR")}
        </span>
      </div>

      <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
        {table.columns.map((c) => {
          const f = famille(c.type);
          const estClef = clefs.has(`${table.name}.${c.name}`);
          return (
            <div key={c.name} className="px-3 py-1.5 flex items-center gap-2">
              <span className={`size-1.5 rounded-full shrink-0 ${f.classe}`} aria-hidden />
              <span
                dir="auto"
                className="text-[11px] font-medium truncate"
                title={c.label ? `${c.name} — ${c.label}` : c.name}
              >
                {c.name}
              </span>
              {estClef && (
                <span
                  className="material-symbols-outlined text-[13px] text-primary shrink-0"
                  title="Colonne servant de lien"
                >
                  key
                </span>
              )}
              {/* Le type est ecrit, pas seulement code par la pastille :
                  la couleur seule ne doit jamais porter l'information. */}
              <span className="ml-auto text-[10px] text-slate-400 shrink-0">{f.court}</span>
            </div>
          );
        })}
      </div>

      {table.columns.some((c) => c.label) && (
        <div className="px-3 py-1.5 border-t border-slate-100 dark:border-slate-800/60">
          {table.columns
            .filter((c) => c.label)
            .slice(0, 4)
            .map((c) => (
              <p key={c.name} className="text-[10px] text-slate-400 truncate">
                {c.name} · <span dir="auto">{c.label}</span>
              </p>
            ))}
        </div>
      )}
    </div>
  );
}

export default function SchemaDiagram({
  tables,
  relations,
}: {
  tables: TableSchema[];
  relations: Relation[];
}) {
  const conteneur = useRef<HTMLDivElement>(null);
  const [largeur, setLargeur] = useState(900);

  useEffect(() => {
    const el = conteneur.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setLargeur(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const clefs = useMemo(() => {
    const s = new Set<string>();
    for (const r of relations) {
      s.add(`${r.source}.${r.colonne_source}`);
      s.add(`${r.cible}.${r.colonne_cible}`);
    }
    return s;
  }, [relations]);

  // La table centrale est celle qui porte le plus de liens ; a egalite, la
  // plus volumineuse. C'est la table de faits dans un schema en etoile.
  const { centre, satellites } = useMemo(() => {
    if (tables.length === 0) return { centre: null, satellites: [] as TableSchema[] };
    const degre = (t: TableSchema) =>
      relations.filter((r) => r.source === t.name || r.cible === t.name).length;
    const triees = [...tables].sort((a, b) => degre(b) - degre(a) || b.rows - a.rows);
    return { centre: triees[0], satellites: triees.slice(1) };
  }, [tables, relations]);

  if (!centre) return null;

  // Une seule table : pas d'etoile a dessiner, la carte se suffit.
  if (satellites.length === 0) {
    return (
      <div ref={conteneur} className="flex justify-center py-4">
        <CarteTable table={centre} centrale={false} clefs={clefs} />
      </div>
    );
  }

  // Positions : le centre au milieu, les satellites sur une ellipse.
  const hauteurCarte = (t: TableSchema) => 40 + t.columns.length * 27 + 12;
  const hMax = Math.max(...tables.map(hauteurCarte));

  // L'angle DEMARRE a gauche (π) : partir du haut placerait les deux
  // satellites d'un schema a trois tables sur le seul axe vertical, donc
  // superposes a la table centrale.
  const angleDe = (i: number) => Math.PI + (2 * Math.PI * i) / satellites.length;

  const rayonX = Math.max(260, Math.min(largeur / 2 - LARGEUR / 2 - 16, 360));
  // Rayon vertical suffisant pour qu'une carte haute ne chevauche jamais la
  // carte centrale ; inutile d'etirer si les satellites sont sur les cotes.
  const surAxeVertical = satellites.some(
    (_, i) => Math.abs(Math.cos(angleDe(i))) < 0.35
  );
  const rayonY = surAxeVertical ? hauteurCarte(centre) / 2 + hMax / 2 + 40 : 150;

  const cx = largeur / 2;
  const positions = new Map<string, { x: number; y: number; h: number }>();
  positions.set(centre.name, {
    x: cx - LARGEUR / 2,
    y: -hauteurCarte(centre) / 2,
    h: hauteurCarte(centre),
  });
  satellites.forEach((t, i) => {
    const angle = angleDe(i);
    positions.set(t.name, {
      x: cx + rayonX * Math.cos(angle) - LARGEUR / 2,
      y: rayonY * Math.sin(angle) - hauteurCarte(t) / 2,
      h: hauteurCarte(t),
    });
  });

  // Hauteur deduite des positions REELLES, pas du rayon : quand tous les
  // satellites sont sur l'axe horizontal, un cadre dimensionne sur le rayon
  // laisserait deux larges bandes vides.
  const hauts = [...positions.values()];
  const minY = Math.min(...hauts.map((p) => p.y));
  const maxY = Math.max(...hauts.map((p) => p.y + p.h));
  // La hauteur des cartes est estimee a partir du nombre de colonnes : on
  // garde une marge, sinon quelques pixels d'ecart font apparaitre une barre
  // de defilement verticale parasite.
  const hauteur = maxY - minY + 48;
  for (const p of positions.values()) p.y += 24 - minY;

  const ancre = (nom: string) => {
    const p = positions.get(nom);
    return p
      ? { x: p.x + LARGEUR / 2, y: p.y + p.h / 2 }
      : { x: cx, y: hauteur / 2 };
  };

  return (
    <div ref={conteneur} className="relative overflow-x-auto">
      <div className="relative mx-auto" style={{ height: hauteur, minWidth: 640 }}>
        <svg
          className="absolute inset-0 pointer-events-none"
          width="100%"
          height={hauteur}
          aria-hidden
        >
          {relations.map((r, i) => {
            const a = ancre(r.source);
            const b = ancre(r.cible);
            const mx = (a.x + b.x) / 2;
            const my = (a.y + b.y) / 2;
            return (
              <g key={i}>
                <path
                  d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
                  fill="none"
                  stroke="var(--viz-axis, #cbd5e1)"
                  strokeWidth={1.6}
                  strokeDasharray="5 4"
                />
                <circle cx={b.x} cy={b.y} r={3.5} fill="var(--viz-series-1, #2a78d6)" />
              </g>
            );
          })}
        </svg>

        {/* Etiquettes des liens, au-dessus des traits mais sous les cartes */}
        {relations.map((r, i) => {
          const a = ancre(r.source);
          const b = ancre(r.cible);
          return (
            <span
              key={`l-${i}`}
              className="absolute -translate-x-1/2 -translate-y-1/2 rounded px-1.5 py-0.5 text-[9.5px] font-medium bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-500 whitespace-nowrap"
              style={{ left: (a.x + b.x) / 2, top: (a.y + b.y) / 2 }}
            >
              {r.colonne_source} → {r.colonne_cible}
            </span>
          );
        })}

        {tables.map((t) => {
          const p = positions.get(t.name)!;
          return (
            <div key={t.name} className="absolute" style={{ left: p.x, top: p.y }}>
              <CarteTable table={t} centrale={t.name === centre.name} clefs={clefs} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
