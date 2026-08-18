/**
 * Adaptation d'un resultat SQL (colonnes + lignes) a une forme de graphique.
 *
 * Meme philosophie que le reste : l'agent PROPOSE une forme, ce code la
 * VALIDE contre la forme reelle des donnees et la corrige au besoin. Un
 * anneau demande sur des valeurs negatives, par exemple, devient des barres.
 */

import { ChartKind, SERIES_MAX } from "./chartTheme";

export type SqlResult = {
  columns: string[];
  rows: Record<string, any>[];
  row_count?: number;
  truncated?: boolean;
};

/** Formes exposees a l'utilisateur, avec le nom employe par les agents. */
export const VIZ_LABELS: Record<string, string> = {
  tuile: "Chiffre clé",
  barres: "Barres",
  barres_horizontales: "Barres horizontales",
  courbe: "Courbe",
  anneau: "Anneau",
  table: "Tableau",
};

const TO_KIND: Record<string, ChartKind | "table"> = {
  tuile: "tile",
  barres: "bar",
  barres_horizontales: "bar_h",
  courbe: "line",
  anneau: "donut",
  table: "table",
};

export type Shaped = {
  kind: ChartKind | "table";
  /** Colonne des libelles (axe des categories ou des dates). */
  xKey: string;
  /** Colonne de la valeur numerique. */
  yKey: string;
  rows: Record<string, any>[];
  /** Valeur unique, pour une tuile. */
  value: number | null;
  /** Somme des valeurs — affichee en sous-titre quand elle a un sens. */
  total: number | null;
};

function isNumeric(v: any): boolean {
  return typeof v === "number" && Number.isFinite(v);
}

/** Une chaine qui ressemble a une date ISO : sert a choisir courbe vs barres. */
function looksLikeDate(v: any): boolean {
  return typeof v === "string" && /^\d{4}-\d{2}(-\d{2})?/.test(v);
}

/**
 * Replie la queue au-dela de 8 categories dans « Autres » : on ne genere
 * jamais une 9e couleur, elle serait indistinguable sous daltonisme.
 */
function foldTail(rows: any[], xKey: string, yKey: string, max = SERIES_MAX): any[] {
  if (rows.length <= max) return rows;
  const head = rows.slice(0, max - 1);
  const tail = rows.slice(max - 1);
  const sum = tail.reduce((s, r) => s + (Number(r[yKey]) || 0), 0);
  return [...head, { [xKey]: `Autres (${tail.length})`, [yKey]: sum }];
}

export function shape(result: SqlResult | null, proposed?: string): Shaped | null {
  if (!result || !result.rows) return null;
  const cols = result.columns || [];
  const rows = result.rows;
  if (cols.length === 0) return null;

  let kind = TO_KIND[proposed || ""] || "table";

  // Une seule cellule -> le nombre EST le graphique, quelle que soit la
  // forme demandee.
  if (rows.length === 1 && cols.length === 1) {
    const v = rows[0][cols[0]];
    return {
      kind: "tile",
      xKey: cols[0],
      yKey: cols[0],
      rows,
      value: isNumeric(v) ? v : Number(v) || null,
      total: null,
    };
  }

  // Plus de 2 colonnes : aucun graphique a deux dimensions ne peut la rendre
  // fidelement -> tableau.
  if (cols.length !== 2) {
    return { kind: "table", xKey: cols[0], yKey: cols[1] ?? cols[0], rows, value: null, total: null };
  }

  const xKey = cols[0];
  const yKey = cols[1];
  const values = rows.map((r) => Number(r[yKey]));
  const allNumeric = values.every((v) => Number.isFinite(v));
  const allPositive = allNumeric && values.every((v) => v >= 0);

  // La valeur n'est pas numerique : rien a tracer.
  if (!allNumeric) {
    return { kind: "table", xKey, yKey, rows, value: null, total: null };
  }

  const labels = rows.map((r) => String(r[xKey] ?? ""));
  const dated = labels.length > 1 && labels.every(looksLikeDate);
  const longest = labels.reduce((m, l) => Math.max(m, l.length), 0);

  if (kind === "tile") kind = dated ? "line" : "bar";
  // Un anneau represente un part-a-tout : valeurs positives, peu de segments.
  if (kind === "donut" && (!allPositive || rows.length > 6)) kind = "bar";
  // Des libelles longs ou nombreux se chevauchent a la verticale.
  if (kind === "bar" && (rows.length > 8 || longest > 12)) kind = "bar_h";
  if (kind === "line" && !dated) kind = rows.length > 8 || longest > 12 ? "bar_h" : "bar";

  const data = kind === "line" ? rows : foldTail(rows, xKey, yKey);
  const total = allPositive ? values.reduce((s, v) => s + v, 0) : null;

  return { kind, xKey, yKey, rows: data, value: null, total };
}
