/** Surface de contenu : un fond, un filet, rien de plus. */
export function Carte({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`panneau-doux p-5 ${className}`}>{children}</section>;
}
