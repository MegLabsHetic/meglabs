/** Panneau de verre. L'épaisseur vient du liseré lumineux, pas d'une bordure épaisse. */
export function Carte({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`verre p-5 ${className}`}>{children}</section>;
}
