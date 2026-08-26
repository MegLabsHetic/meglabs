/**
 * Le résultat d'une question, montré plutôt que listé.
 *
 * L'orchestrateur décide déjà si un graphique éclaire la réponse — c'est le champ
 * `besoin_visualisation`. Ce composant ne redécide pas : il regarde la forme des
 * données et choisit la représentation, ou s'abstient. Un graphique qui ne se lit
 * pas vaut moins que le tableau, qui reste disponible juste en dessous.
 *
 * Aucune bibliothèque : une barre est une div dont la largeur est un pourcentage,
 * une courbe est un `polyline`. Ajouter une dépendance de graphiques pour ça
 * coûterait des centaines de kilooctets et romprait avec le reste du front.
 */
"use client";

import { useId, useState } from "react";

type Valeur = string | number | null;

/** Au-delà, les libellés se chevauchent et le tableau redevient plus lisible. */
const MAX_BARRES = 12;
const MAX_POINTS = 60;

/** Une année, un mois ou une date ISO : la question porte alors sur une évolution. */
const TEMPOREL = /^(\d{4}|\d{4}-\d{2}(-\d{2})?|\d{2}\/\d{2}\/\d{4})$/;

const FORMAT = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });

function nombre(valeur: Valeur): number | null {
  if (valeur === null || valeur === "") return null;
  const parse = typeof valeur === "number" ? valeur : Number(String(valeur).replace(",", "."));
  return Number.isFinite(parse) ? parse : null;
}

type Serie = {
  forme: "barres" | "courbe";
  libelleAxe: string;
  mesure: string;
  points: { libelle: string; valeur: number }[];
};

type Tuiles = {
  forme: "tuiles";
  chiffres: { mesure: string; valeur: number }[];
  /** Ce que la ligne unique qualifie, s'il y a une colonne textuelle. */
  qualifiant: string | null;
};

type Vue = Serie | Tuiles;

/** Au-delà, ce n'est plus un chiffre clé mais un tableau à une ligne. */
const MAX_TUILES = 4;

/**
 * Une seule ligne n'est pas un graphique, c'est un résultat.
 *
 * « Quel est le salaire moyen ? » renvoie une valeur : la dessiner en barre
 * n'apprend rien, puisqu'il n'y a rien à comparer. Le chiffre en grand est la
 * bonne réponse — et sans cette forme, ces questions n'affichaient rien du tout.
 */
function tuiles(colonnes: string[], ligne: Valeur[]): Tuiles | null {
  const chiffres = colonnes
    .map((mesure, colonne) => ({ mesure, valeur: nombre(ligne[colonne]) }))
    .filter((chiffre): chiffre is { mesure: string; valeur: number } => chiffre.valeur !== null);

  if (chiffres.length === 0 || chiffres.length > MAX_TUILES) return null;

  const textuelle = colonnes.findIndex((_, colonne) => nombre(ligne[colonne]) === null);
  const qualifiant = textuelle === -1 ? null : String(ligne[textuelle] ?? "");

  return { forme: "tuiles", chiffres, qualifiant: qualifiant || null };
}

/**
 * Choisit la forme à partir des données, pas d'un réglage.
 *
 * Exactement deux colonnes : c'est ce que produit un `GROUP BY`, et c'est ce
 * qui distingue une répartition d'une liste d'enregistrements. Trois colonnes
 * ou plus, on ne dessine pas — on ne saurait pas laquelle porte le sens.
 *
 * Le nombre de lignes fait le reste du tri : une seule ligne est un total ou un
 * pourcentage, et un total ne se dessine pas ; au-delà d'une douzaine de
 * catégories les libellés se chevauchent et le tableau redevient plus lisible.
 */
function analyser(colonnes: string[], lignes: Valeur[][]): Vue | null {
  if (colonnes.length === 0 || lignes.length === 0) return null;
  if (lignes.length === 1) return tuiles(colonnes, lignes[0]);
  if (colonnes.length !== 2) return null;

  const indexMesure = colonnes.findIndex((_, colonne) =>
    lignes.every((ligne) => nombre(ligne[colonne]) !== null),
  );
  if (indexMesure === -1) return null;

  const indexLibelle = colonnes.findIndex((_, colonne) => colonne !== indexMesure);
  if (indexLibelle === -1) return null;

  const points = lignes
    .map((ligne) => ({
      libelle: ligne[indexLibelle] === null ? "—" : String(ligne[indexLibelle]),
      valeur: nombre(ligne[indexMesure]) ?? 0,
    }))
    .filter((point) => Number.isFinite(point.valeur));

  if (points.length < 2) return null;

  const temporel = points.every((point) => TEMPOREL.test(point.libelle));
  const forme = temporel && points.length > 3 ? "courbe" : "barres";

  if (forme === "barres" && points.length > MAX_BARRES) return null;
  if (forme === "courbe" && points.length > MAX_POINTS) return null;
  // Une mesure entièrement négative ou nulle ne se lit pas en longueur de barre.
  if (forme === "barres" && points.every((point) => point.valeur <= 0)) return null;

  return {
    forme,
    libelleAxe: colonnes[indexLibelle],
    mesure: colonnes[indexMesure],
    points,
  };
}

/**
 * Le chiffre en grand, et son nom en petit dessous.
 *
 * L'ordre importe : on lit la valeur avant de lire ce qu'elle mesure. L'inverse
 * oblige à parcourir un libellé pour arriver à l'information.
 */
function Chiffres({ vue }: { vue: Tuiles }) {
  return (
    <div className="flex flex-wrap gap-x-10 gap-y-4">
      {vue.chiffres.map((chiffre) => (
        <div key={chiffre.mesure} className="flex flex-col gap-0.5">
          <span
            className="chiffres-alignes text-3xl leading-none"
            style={{ color: "var(--accent-clair)" }}
          >
            {FORMAT.format(chiffre.valeur)}
          </span>
          <span className="text-xs" style={{ color: "var(--ink-muted)" }}>
            {chiffre.mesure}
            {vue.qualifiant && ` · ${vue.qualifiant}`}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Barres horizontales, et non verticales : les libellés sont des mots français
 * — « Ressources humaines », « Commercial » — qu'une barre verticale tronque ou
 * fait pivoter. À l'horizontale ils se lisent normalement.
 *
 * Pas d'axe des valeurs : chaque barre porte son chiffre, ce qui rend la grille
 * inutile et retire une couche de bruit.
 */
function Barres({ serie }: { serie: Serie }) {
  const [survolee, setSurvolee] = useState<number | null>(null);
  const maximum = Math.max(...serie.points.map((point) => point.valeur));

  return (
    <div className="flex flex-col gap-1.5">
      {serie.points.map((point, rang) => {
        const part = maximum > 0 ? Math.max((point.valeur / maximum) * 100, 1.5) : 0;
        const actif = survolee === rang;
        return (
          <div
            key={`${point.libelle}-${rang}`}
            className="grid items-center gap-3"
            style={{ gridTemplateColumns: "minmax(0, 8rem) 1fr auto" }}
            onMouseEnter={() => setSurvolee(rang)}
            onMouseLeave={() => setSurvolee(null)}
          >
            <span
              className="truncate text-xs"
              style={{ color: actif ? "var(--ink-1)" : "var(--ink-2)" }}
              title={point.libelle}
            >
              {point.libelle}
            </span>

            {/* La piste rend visible la part que la barre n'occupe pas. */}
            <span
              className="block h-5 rounded-sm"
              style={{ background: "var(--voile)" }}
              aria-hidden
            >
              <span
                className="block h-full rounded-sm"
                style={{
                  width: `${part}%`,
                  background: actif ? "var(--accent-clair)" : "var(--accent)",
                  transition: "width var(--duree) var(--sortie), background var(--duree-courte)",
                }}
              />
            </span>

            <span
              className="chiffres-alignes text-xs tabular-nums"
              style={{ color: actif ? "var(--ink-1)" : "var(--ink-2)" }}
            >
              {FORMAT.format(point.valeur)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Une courbe pour une évolution. Seuls le premier, le dernier et l'extremum
 * portent leur valeur : annoter chaque point rendrait la ligne illisible, alors
 * que ces trois-là suffisent à situer l'échelle.
 */
function Courbe({ serie }: { serie: Serie }) {
  const identifiant = useId();
  const valeurs = serie.points.map((point) => point.valeur);
  const haut = Math.max(...valeurs);
  const bas = Math.min(...valeurs);
  const amplitude = haut - bas || 1;

  const largeur = 100;
  const hauteur = 34;
  const coordonnees = serie.points.map((point, rang) => {
    const x = (rang / (serie.points.length - 1)) * largeur;
    const y = hauteur - ((point.valeur - bas) / amplitude) * hauteur;
    return { ...point, x, y };
  });

  const trace = coordonnees.map(({ x, y }) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const rangHaut = valeurs.indexOf(haut);
  const marques = new Set([0, coordonnees.length - 1, rangHaut]);

  return (
    <div className="flex flex-col gap-2">
      <svg
        viewBox={`-2 -4 ${largeur + 4} ${hauteur + 8}`}
        className="h-32 w-full"
        preserveAspectRatio="none"
        role="img"
        aria-labelledby={identifiant}
      >
        <title id={identifiant}>
          {`Évolution de ${serie.mesure}, de ${FORMAT.format(valeurs[0])} à ${FORMAT.format(
            valeurs[valeurs.length - 1],
          )}`}
        </title>
        <polyline
          points={trace}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        {coordonnees.map(({ x, y }, rang) =>
          marques.has(rang) ? (
            <circle
              key={rang}
              cx={x}
              cy={y}
              r={2.5}
              fill="var(--accent-clair)"
              stroke="var(--panneau)"
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
          ) : null,
        )}
      </svg>

      <div className="flex justify-between text-xs" style={{ color: "var(--ink-muted)" }}>
        {coordonnees.map(({ libelle, valeur }, rang) =>
          marques.has(rang) ? (
            <span key={rang} className="chiffres-alignes">
              {libelle} · {FORMAT.format(valeur)}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}

/**
 * L'orchestrateur renvoie aussi son avis, dans `besoin_visualisation`. On ne s'en
 * sert pas pour décider, et c'est délibéré : mesuré sur « combien de
 * collaborateurs par service », il a répondu `false` sur une répartition en cinq
 * catégories — le cas que son propre prompt donne en exemple de `true`.
 *
 * C'est la règle de l'Agent Data appliquée à l'affichage : ce qui se calcule ne
 * se demande pas à un modèle. La forme du résultat est un fait, pas un jugement.
 *
 * Le prix de ce choix : une colonne numérique qui serait un identifiant se
 * dessinerait quand même. C'est rare, et moins coûteux que de ne jamais rien
 * afficher. L'écart entre les deux décisions se journalise, et donne une
 * métrique de plus sur la fiabilité de l'orchestrateur.
 */
export function Graphique({ colonnes, lignes }: { colonnes: string[]; lignes: Valeur[][] }) {
  const vue = analyser(colonnes, lignes);
  if (vue === null) return null;

  if (vue.forme === "tuiles") {
    return (
      <figure className="mt-4">
        <Chiffres vue={vue} />
      </figure>
    );
  }

  return (
    <figure className="mt-4 flex flex-col gap-3">
      <figcaption className="text-xs" style={{ color: "var(--ink-muted)" }}>
        {vue.mesure} par {vue.libelleAxe}
      </figcaption>
      {vue.forme === "barres" ? <Barres serie={vue} /> : <Courbe serie={vue} />}
    </figure>
  );
}
