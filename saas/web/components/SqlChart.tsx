"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  SERIES_1,
  VIZ,
  couleurChoisie,
  fmt,
  fmtAxis,
  fmtCompact,
  fmtDate,
  indicesEntoures,
  series,
  type Apparence,
} from "@/lib/chartTheme";
import { SqlResult, shape } from "@/lib/sqlViz";

/**
 * Rendu d'un resultat SQL dans la forme demandee.
 *
 * Regles de la charte de visualisation : marques fines, bouts arrondis 4px
 * ancres a la ligne de base, traits 2px, grille recessive, infobulle
 * systematique, legende des 2 series, et une vue tableau jumelle toujours
 * accessible — chaque valeur reste lisible sans dependre de la couleur.
 */

const AXIS_TICK = { fill: VIZ.inkMuted, fontSize: 11 };
const MARGIN = { top: 8, right: 12, left: 4, bottom: 0 };

function TooltipBox({ active, payload, label, format, isDate }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs shadow-lg"
      style={{ background: VIZ.tooltipBg, border: `1px solid ${VIZ.tooltipRing}`, color: VIZ.ink }}
    >
      <div style={{ color: VIZ.inkMuted }}>{isDate ? fmtDate(label) : label}</div>
      <div className="font-semibold mt-0.5">{fmt(payload[0].value, format)}</div>
    </div>
  );
}

function TableView({ result }: { result: SqlResult }) {
  return (
    <div className="max-h-[280px] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white dark:bg-slate-900">
          <tr className="text-left border-b border-slate-200 dark:border-slate-800">
            {result.columns.map((c) => (
              <th key={c} className="py-1.5 pr-3 font-semibold text-slate-500 dark:text-slate-400">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((r, i) => (
            <tr key={i} className="border-b border-slate-100 dark:border-slate-800/60">
              {result.columns.map((c) => (
                <td
                  key={c}
                  className={`py-1.5 pr-3 ${typeof r[c] === "number" ? "tabular-nums" : ""}`}
                >
                  <span dir="auto">{typeof r[c] === "number" ? fmt(r[c]) : String(r[c] ?? "—")}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {result.truncated && (
        <p className="text-xs text-slate-400 mt-2">Affichage limité aux premières lignes.</p>
      )}
    </div>
  );
}

/** Chiffre cle : le nombre EST le graphique. */
export function Tile({
  title,
  value,
  format,
  erreur,
}: {
  title: string;
  value: number | null;
  format?: string;
  erreur?: string | null;
}) {
  return (
    <div className="viz-root bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 h-full">
      {erreur ? (
        <>
          <p className="text-xl font-bold tracking-tight text-slate-400">—</p>
          <p className="text-xs mt-1 text-amber-600 dark:text-amber-500" title={erreur}>
            Non calculable
          </p>
        </>
      ) : (
        // Abrege a l'affichage, exact au survol : on abrege le rendu, jamais
        // la donnee.
        <p
          className="text-2xl font-bold tracking-tight"
          style={{ color: VIZ.ink }}
          title={fmt(value, format)}
        >
          {fmtCompact(value, format)}
        </p>
      )}
      <p dir="auto" className="text-slate-500 dark:text-slate-400 text-xs mt-1">{title}</p>
    </div>
  );
}

export default function SqlChart({
  title,
  result,
  viz,
  format,
  erreur,
  sql,
  actions,
  style,
}: {
  title: string;
  result: SqlResult | null;
  viz?: string;
  format?: string;
  erreur?: string | null;
  /** Affiche le SQL execute — l'analyse doit rester auditable. */
  sql?: string;
  actions?: React.ReactNode;
  /** Apparence demandee par l'utilisateur : couleur, pics entoures, etiquettes. */
  style?: Apparence | null;
}) {
  const [view, setView] = useState<"chart" | "table" | "sql">("chart");
  const shaped = shape(result, viz);

  if (erreur || !shaped) {
    return (
      <div className="viz-root bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
        <div className="flex items-start justify-between gap-3">
          <h4 className="text-sm font-semibold leading-tight">{title}</h4>
          {actions}
        </div>
        <div className="py-8 flex flex-col items-center text-center">
          <span className="material-symbols-outlined text-3xl text-amber-500 mb-2">
            error_outline
          </span>
          <p className="text-sm font-medium">Cet indicateur n&apos;a pas pu être calculé</p>
          {erreur && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{erreur}</p>}
        </div>
        {sql && (
          <pre className="mt-2 text-[11px] bg-slate-100 dark:bg-slate-800 rounded-lg p-3 overflow-x-auto">
            {sql}
          </pre>
        )}
      </div>
    );
  }

  if (shaped.kind === "tile" && !actions && !sql) {
    return <Tile title={title} value={shaped.value} format={format} />;
  }

  const { kind, xKey, yKey, rows } = shaped;
  const isDate = kind === "line";
  const tip = <Tooltip content={<TooltipBox format={format} isDate={isDate} />} />;
  const grid = <CartesianGrid stroke={VIZ.grid} vertical={false} />;
  const chartRows: Record<string, any>[] = rows.map((r) => ({ ...r, __v: Number(r[yKey]) }));

  // Apparence demandee. `choisie` vaut null tant que l'utilisateur n'a rien
  // dit : on garde alors la palette validee, dans son ordre.
  const choisie = couleurChoisie(style);
  const entoures = indicesEntoures(chartRows.map((r) => r.__v), style?.entourer);
  const teinteBarre = (i: number) => choisie || series(i);
  // Un pic entoure ou une valeur posee sur la marque depasse vers le haut :
  // sans marge, l'etiquette du point le plus haut est coupee par le bord.
  const margeHaut = entoures.length || style?.etiquettes ? 26 : MARGIN.top;
  const sommet = entoures.length ? Math.max(...chartRows.map((r) => r.__v)) : null;
  /**
   * Etiquette de valeur sur la marque, si elle a ete demandee.
   *
   * Le trace est repris a la main : par defaut, Recharts contraint le texte a
   * la largeur de la barre et renvoie « € » a la ligne des que la valeur est
   * un peu longue — « 32 625 » au-dessus de « € », illisible.
   */
  const etiquette = (ou: "haut" | "droite") => (props: any) => {
    const { x, y, width = 0, height = 0, value } = props;
    const droite = ou === "droite";
    return (
      <text
        x={droite ? x + width + 6 : x + width / 2}
        y={droite ? y + height / 2 + 4 : y - 6}
        textAnchor={droite ? "start" : "middle"}
        fill={VIZ.inkSecondary}
        fontSize={11}
      >
        {fmtCompact(Number(value), format)}
      </text>
    );
  };
  const etiquettes = style?.etiquettes ? (
    <LabelList dataKey="__v" content={etiquette("haut")} />
  ) : null;

  const chart = () => {
    if (kind === "tile") {
      return (
        <p
          className="text-3xl font-bold tracking-tight py-6"
          style={{ color: VIZ.ink }}
          title={fmt(shaped.value, format)}
        >
          {fmtCompact(shaped.value, format)}
        </p>
      );
    }
    if (kind === "table" || !rows.length) {
      return result ? <TableView result={result} /> : null;
    }
    if (kind === "donut") {
      return (
        <ResponsiveContainer width="100%" height={240}>
          <PieChart margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
            <Pie
              data={chartRows}
              dataKey="__v"
              nameKey={xKey}
              innerRadius="55%"
              outerRadius="82%"
              paddingAngle={2}
              stroke={VIZ.surface}
              strokeWidth={2}
            >
              {/* L'anneau garde la palette catégorielle même si une couleur a
                  été demandée : ce sont les teintes qui distinguent les parts,
                  les peindre toutes pareil effacerait le graphique. Le refus
                  est expliqué à l'utilisateur au moment de la demande. */}
              {chartRows.map((_, i) => (
                <Cell key={i} fill={series(i)} />
              ))}
            </Pie>
            <Legend
              verticalAlign="bottom"
              height={28}
              iconType="circle"
              iconSize={8}
              formatter={(v) => <span style={{ color: VIZ.inkSecondary, fontSize: 12 }}>{v}</span>}
            />
            {tip}
          </PieChart>
        </ResponsiveContainer>
      );
    }
    if (kind === "bar_h") {
      const h = Math.max(200, chartRows.length * 30 + 32);
      return (
        <ResponsiveContainer width="100%" height={h}>
          <BarChart
            data={chartRows}
            layout="vertical"
            margin={{ ...MARGIN, left: 8, right: style?.etiquettes ? 44 : MARGIN.right }}
            barCategoryGap={4}
          >
            <CartesianGrid stroke={VIZ.grid} horizontal={false} />
            <XAxis
              type="number"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: VIZ.axis }}
              tickFormatter={(v) => fmtAxis(v, format)}
            />
            <YAxis
              type="category"
              dataKey={xKey}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: VIZ.axis }}
              width={120}
            />
            {tip}
            {/* Une couleur par categorie. L'ordre des slots est fixe : c'est
                lui qui garantit la lisibilite sous daltonisme, et la queue
                au-dela de 8 est deja repliee dans « Autres ». */}
            <Bar dataKey="__v" radius={[0, 4, 4, 0]} maxBarSize={22}>
              {chartRows.map((_, i) => (
                <Cell
                  key={i}
                  fill={teinteBarre(i)}
                  // La barre mise en evidence est cerclee d'un trait d'encre :
                  // repere lisible sans dependre de la couleur.
                  stroke={entoures.includes(i) ? VIZ.ink : undefined}
                  strokeWidth={entoures.includes(i) ? 2 : 0}
                />
              ))}
              {style?.etiquettes && (
                <LabelList dataKey="__v" content={etiquette("droite")} />
              )}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      );
    }
    if (kind === "bar") {
      const angled = chartRows.length > 6;
      return (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={chartRows}
            margin={{ ...MARGIN, top: margeHaut, bottom: angled ? 22 : 0 }}
            barCategoryGap={4}
          >
            {grid}
            <XAxis
              dataKey={xKey}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: VIZ.axis }}
              interval={0}
              angle={angled ? -25 : 0}
              textAnchor={angled ? "end" : "middle"}
              height={angled ? 52 : 28}
            />
            <YAxis
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={52}
              tickFormatter={(v) => fmtAxis(v, format)}
            />
            {tip}
            <Bar dataKey="__v" radius={[4, 4, 0, 0]} maxBarSize={44}>
              {chartRows.map((_, i) => (
                <Cell
                  key={i}
                  fill={teinteBarre(i)}
                  stroke={entoures.includes(i) ? VIZ.ink : undefined}
                  strokeWidth={entoures.includes(i) ? 2 : 0}
                />
              ))}
              {etiquettes}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      );
    }
    return (
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartRows} margin={{ ...MARGIN, top: margeHaut }}>
          {grid}
          <XAxis
            dataKey={xKey}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: VIZ.axis }}
            tickFormatter={fmtDate}
            minTickGap={24}
          />
          <YAxis
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={52}
            tickFormatter={(v) => fmtAxis(v, format)}
          />
          {tip}
          <Line
            type="monotone"
            dataKey="__v"
            stroke={choisie || SERIES_1}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: VIZ.surface }}
          >
            {etiquettes}
          </Line>
          {/* Pic ou creux entoure : un cercle vide pose sur le point, avec sa
              valeur. Le cercle est en couleur de trace, l'anneau exterieur en
              couleur de fond pour qu'il se detache meme sur la courbe. */}
          {entoures.map((i) => (
            <ReferenceDot
              key={i}
              x={chartRows[i][xKey]}
              y={chartRows[i].__v}
              r={7}
              fill="none"
              stroke={choisie || SERIES_1}
              strokeWidth={2}
              isFront
              label={{
                value: fmtCompact(chartRows[i].__v, format),
                // La valeur d'un creux se pose SOUS le point : au-dessus,
                // elle tomberait sur la courbe qui remonte.
                position: chartRows[i].__v === sommet ? "top" : "bottom",
                offset: 12,
                fill: VIZ.ink,
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const Toggle = ({ mode, icon, label }: { mode: typeof view; icon: string; label: string }) => (
    <button
      onClick={() => setView(view === mode ? "chart" : mode)}
      title={label}
      aria-label={label}
      className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors ${
        view === mode
          ? "text-primary bg-primary/10"
          : "text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-800"
      }`}
    >
      <span className="material-symbols-outlined text-base">{icon}</span>
    </button>
  );

  return (
    <div className="viz-root bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h4 dir="auto" className="text-sm font-semibold leading-tight truncate">{title}</h4>
          {shaped.total != null && kind !== "tile" && (
            <p
              className="text-xs text-slate-500 dark:text-slate-400 mt-0.5"
              title={fmt(shaped.total, format)}
            >
              Total : {fmtCompact(shaped.total, format)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          {kind !== "table" && <Toggle mode="table" icon="table_rows" label="Afficher les valeurs" />}
          {sql && <Toggle mode="sql" icon="code" label="Voir la requête SQL" />}
          {actions}
        </div>
      </div>

      {view === "sql" && sql ? (
        <pre className="text-[11px] leading-relaxed bg-slate-100 dark:bg-slate-800 rounded-lg p-3 overflow-x-auto">
          {sql}
        </pre>
      ) : view === "table" && result ? (
        <TableView result={result} />
      ) : (
        chart()
      )}
    </div>
  );
}
