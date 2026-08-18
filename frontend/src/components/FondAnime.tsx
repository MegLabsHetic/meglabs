/**
 * Fond : deux halos très diffus et une trame fine.
 *
 * Volontairement discret. Une grille animée derrière un tableau de chiffres fatigue
 * l'œil et fait « démo » ; ici le fond donne de la profondeur et se tait. Aucun
 * canvas, aucune image d'animation — c'est du CSS, donc gratuit.
 */
export function FondAnime() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute -top-1/4 left-1/2 h-[760px] w-[1100px] -translate-x-1/2 rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(63,191,174,0.10), transparent 62%)",
        }}
      />
      <div
        className="absolute bottom-0 right-0 h-[620px] w-[620px] translate-x-1/4 translate-y-1/3 rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle at center, rgba(95,214,198,0.07), transparent 65%)",
        }}
      />
      {/* Trame : elle donne une matière au fond sans jamais entrer en concurrence
          avec le contenu. */}
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(var(--filet) 1px, transparent 1px), linear-gradient(90deg, var(--filet) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          maskImage: "radial-gradient(ellipse 80% 55% at 50% 0%, #000 30%, transparent 78%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 80% 55% at 50% 0%, #000 30%, transparent 78%)",
        }}
      />
    </div>
  );
}
