/**
 * Thème et règles de choix de forme pour tous les graphiques.
 *
 * Les couleurs vivent dans globals.css (`.viz-root`) sous forme de variables CSS :
 * le passage clair/sombre se fait par la cascade, jamais en JavaScript. Aucun
 * composant ne doit contenir de hex en dur.
 */

/** Rôles de couleur — à référencer, jamais à recopier. */
export const VIZ = {
  surface: "var(--viz-surface)",
  ink: "var(--viz-ink)",
  inkSecondary: "var(--viz-ink-secondary)",
  inkMuted: "var(--viz-ink-muted)",
  grid: "var(--viz-grid)",
  axis: "var(--viz-axis)",
  tooltipBg: "var(--viz-tooltip-bg)",
  tooltipRing: "var(--viz-tooltip-ring)",
} as const;

/**
 * Slot catégoriel 1..8. L'ordre est le mécanisme de sûreté daltonisme :
 * on assigne en séquence, on ne cycle jamais. Au-delà de 8, le reste est
 * replié dans « Autres » (voir foldTail) — jamais une 9e teinte générée.
 */
export const SERIES_MAX = 8;
export function series(i: number): string {
  return `var(--viz-series-${Math.min(i, SERIES_MAX - 1) + 1})`;
}

/** Une seule série = un seul slot (slot 1). Des catégories nominales ne se
 *  colorent pas par leur valeur : la longueur de la barre le dit déjà. */
export const SERIES_1 = series(0);

// ──────────────────────────────────────────────
// Apparence demandée par l'utilisateur
// ──────────────────────────────────────────────

/**
 * Apparence d'un indicateur : ce qui se demande en mots dans l'atelier.
 * Le contenu est validé côté serveur (liste fermée) — voir `apparence.py`.
 */
export type Apparence = {
  couleur?: string | null;
  entourer?: "max" | "min" | "extremes" | null;
  etiquettes?: boolean;
};

/** Rang des huit teintes nommées, dans l'ordre fixe de la palette. */
const NOMS: Record<string, number> = {
  bleu: 1, orange: 2, aqua: 3, jaune: 4, magenta: 5, vert: 6, violet: 7, rouge: 8,
};

/**
 * Couleur choisie, ou `null` si l'indicateur garde la palette par défaut.
 *
 * Un nom devient une variable CSS : la teinte suit alors le thème clair ou
 * sombre, chacun ayant sa version validée. Un hexadécimal, lui, est figé —
 * c'est pourquoi il n'est accepté que si l'utilisateur l'a demandé lui-même.
 */
export function couleurChoisie(style?: Apparence | null): string | null {
  const c = style?.couleur;
  if (!c) return null;
  if (NOMS[c]) return `var(--viz-series-${NOMS[c]})`;
  return /^#[0-9a-fA-F]{6}$/.test(c) ? c : null;
}

/** Index des points à entourer, selon la mise en évidence demandée. */
export function indicesEntoures(valeurs: number[], entourer?: string | null): number[] {
  if (!entourer || !valeurs.length) return [];
  const utiles = valeurs.map((v, i) => [v, i] as const).filter(([v]) => Number.isFinite(v));
  if (!utiles.length) return [];
  const max = utiles.reduce((a, b) => (b[0] > a[0] ? b : a));
  const min = utiles.reduce((a, b) => (b[0] < a[0] ? b : a));
  if (entourer === "max") return [max[1]];
  if (entourer === "min") return [min[1]];
  // « extremes » : le sommet et le creux, sauf s'ils se confondent.
  return max[1] === min[1] ? [max[1]] : [max[1], min[1]];
}

// ──────────────────────────────────────────────
// Formatage
// ──────────────────────────────────────────────

/**
 * Valeur EXACTE, lisible en français. C'est la forme de référence : celle
 * des tableaux, des infobulles et de tout endroit où le chiffre doit être
 * vérifiable au centime près.
 *
 * Chiffres proportionnels (pas de tabular-nums sur les grands nombres
 * isolés : `121` paraîtrait espacé).
 */
export function fmt(v: number | null | undefined, format?: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (format === "pourcentage") {
    const p = Math.abs(v) <= 1.5 ? v * 100 : v;
    return p.toFixed(1).replace(".", ",") + " %";
  }
  let s =
    Math.abs(v) >= 1000
      ? Math.round(v).toLocaleString("fr-FR")
      : (Math.round(v * 100) / 100).toString().replace(".", ",");
  if (format === "monetaire") s += " €";
  return s;
}

/** Abréviations d'échelle, du plus grand au plus petit. */
const ECHELLES: Array<[number, string]> = [
  [1e12, "Bn"], // billion (10^12)
  [1e9, "Md"],
  [1e6, "M"],
  [1e3, "k"],
];

/**
 * Valeur ABRÉGÉE, pour les chiffres clés et les totaux.
 *
 * « 1 284 730 € » se lit mal d'un coup d'œil : on compte les chiffres au
 * lieu de lire la grandeur. « 1,28 M€ » se saisit immédiatement.
 *
 * Le seuil est à un million, pas à mille : « 75 221 € » reste parfaitement
 * lisible et l'abréger ferait perdre de la précision pour rien.
 *
 * La valeur exacte reste accessible partout ailleurs (vue tableau,
 * infobulle, attribut title) — on abrège l'affichage, jamais la donnée.
 */
export function fmtCompact(v: number | null | undefined, format?: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (format === "pourcentage") return fmt(v, format);

  const abs = Math.abs(v);
  if (abs < 1e6) return fmt(v, format);

  const [seuil, suffixe] = ECHELLES.find(([s]) => abs >= s)!;
  const reduit = v / seuil;
  // Deux décimales sous 10, une seule au-delà : « 1,28 M » et « 12,8 M »
  // gardent le même nombre de caractères significatifs.
  const decimales = Math.abs(reduit) < 10 ? 2 : 1;
  const nombre = reduit.toFixed(decimales).replace(".", ",").replace(/,?0+$/, "");
  const unite = format === "monetaire" ? ` ${suffixe}€` : ` ${suffixe}`;
  return nombre + unite;
}

/** Graduations d'axe : compactes pour rester lisibles sous la marque. */
export function fmtAxis(v: number, format?: string): string {
  if (v == null || Number.isNaN(v)) return "";
  if (format === "pourcentage") {
    const p = Math.abs(v) <= 1.5 ? v * 100 : v;
    return Math.round(p) + " %";
  }
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(1).replace(".", ",") + " Md";
  if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(".", ",") + " M";
  if (a >= 1_000) return (v / 1_000).toFixed(a >= 10_000 ? 0 : 1).replace(".", ",") + " k";
  return String(Math.round(v * 100) / 100).replace(".", ",");
}

/** Libellé d'axe temporel : on coupe l'horodatage ISO. */
export function fmtDate(v: any): string {
  return String(v ?? "").slice(0, 10);
}

// ──────────────────────────────────────────────
// Choix de la forme (déterministe)
// ──────────────────────────────────────────────

/**
 * Formes de rendu. Le choix effectif est fait dans `lib/sqlViz.ts` : l'agent
 * propose une forme, le code la valide contre la forme réelle du résultat SQL.
 */
export type ChartKind = "tile" | "bar" | "bar_h" | "line" | "area" | "donut";
