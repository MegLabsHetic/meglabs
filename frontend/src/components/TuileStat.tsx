/**
 * Tuile de statistique : un libellé, une valeur.
 *
 * Les grands nombres isolés gardent les chiffres proportionnels — les chiffres
 * tabulaires donnent à chaque caractère la largeur d'un zéro, ce qui fait
 * « flotter » un nombre affiché en grand.
 */
export function TuileStat({
  libelle,
  valeur,
  precision,
}: {
  libelle: string;
  valeur: string;
  precision?: string;
}) {
  return (
    <div
      className="rounded-xl border px-4 py-3.5"
      style={{ background: "var(--surface-1)", borderColor: "var(--bordure)" }}
    >
      <div className="text-[13px]" style={{ color: "var(--ink-2)" }}>
        {libelle}
      </div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{valeur}</div>
      {precision && (
        <div className="mt-0.5 text-xs" style={{ color: "var(--ink-muted)" }}>
          {precision}
        </div>
      )}
    </div>
  );
}
