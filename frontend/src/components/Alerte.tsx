/** Message d'erreur. L'icône double la couleur : elle seule ne suffit jamais. */
export function Alerte({ message }: { message: string }) {
  return (
    <div
      className="flex items-start gap-3 rounded-xl border p-4 text-sm"
      style={{
        background: "color-mix(in oklab, var(--etat-faible) 6%, var(--surface-1))",
        borderColor: "color-mix(in oklab, var(--etat-faible) 35%, var(--bordure))",
      }}
      role="alert"
    >
      <span aria-hidden className="pt-0.5" style={{ color: "var(--etat-faible)" }}>
        ■
      </span>
      <p>{message}</p>
    </div>
  );
}
