"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Apparition au defilement.
 *
 * L'etat initial (opacite 0, decalage) vit dans `globals.css` : si le
 * JavaScript ne demarre pas, un `noscript` remet tout visible plutot que de
 * laisser une page blanche. On observe une seule fois, puis on se detache —
 * un observateur laisse tourner sur une page vitrine ne sert a rien.
 */
export default function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: any;
}) {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Si l'element est deja dans l'ecran au chargement, on n'attend pas.
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <Tag
      ref={ref}
      className={`lp-reveal ${shown ? "is-in" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}
