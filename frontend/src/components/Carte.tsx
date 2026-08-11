/** Surface de contenu : un fond, un filet, rien de plus. */
export function Carte({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border p-5 ${className}`}
      style={{ background: "var(--surface-1)", borderColor: "var(--bordure)" }}
    >
      {children}
    </section>
  );
}
