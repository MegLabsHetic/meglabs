/**
 * Squelettes de chargement.
 *
 * Un squelette dit « ça arrive, et voilà la forme que ça aura ». Un texte
 * « chargement… » ne dit que « attends ». La différence se voit surtout quand la
 * réponse est lente : l'écran reste construit au lieu de sauter.
 */
export function Ligne({ largeur = "100%", hauteur = 12 }: { largeur?: string; hauteur?: number }) {
  return <div className="squelette" style={{ width: largeur, height: hauteur }} />;
}

export function SqueletteProfil() {
  return (
    <div className="space-y-6" aria-hidden>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((rang) => (
          <div key={rang} className="panneau-doux space-y-3 px-4 py-3.5">
            <Ligne largeur="55%" hauteur={10} />
            <Ligne largeur="40%" hauteur={26} />
            <Ligne largeur="70%" hauteur={9} />
          </div>
        ))}
      </div>

      <div className="panneau-doux flex flex-wrap items-center gap-8 p-5">
        <div
          className="squelette shrink-0 rounded-full"
          style={{ width: 180, height: 180 }}
        />
        <div className="min-w-60 flex-1 space-y-3">
          <Ligne largeur="35%" hauteur={10} />
          <Ligne />
          <Ligne largeur="85%" />
          <Ligne largeur="70%" />
        </div>
      </div>

      <div className="panneau-doux space-y-3 p-5">
        <Ligne largeur="25%" hauteur={10} />
        {[0, 1, 2, 3, 4, 5].map((rang) => (
          <Ligne key={rang} hauteur={18} />
        ))}
      </div>
    </div>
  );
}
