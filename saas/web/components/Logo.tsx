/**
 * Identite visuelle DataVox, redessinee en vectoriel.
 *
 * Le signe est une bulle de dialogue (la parole) qui contient un histogramme
 * et une onde (la donnee) : c'est exactement le produit — on parle, les
 * donnees repondent.
 *
 * Redessine en primitives SVG plutot que vectorise depuis l'image : le trace
 * reste net a toutes les tailles, pese quelques centaines d'octets, et ses
 * couleurs restent modifiables.
 */

const BLEU_CLAIR = "#6db2ff";
const BLEU = "#2f7ce0";
const BLEU_FONCE = "#1550ad";
const CYAN = "#63e2ff";
const FOND = "#0b1729";

/**
 * Signe seul. `id` prefixe les identifiants internes : deux logos sur la
 * meme page partageraient sinon leurs degrades et leurs filtres.
 */
export function LogoMark({
  size = 32,
  id = "dv",
  className = "",
}: {
  size?: number;
  id?: string;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      role="img"
      aria-label="DataVox"
    >
      <defs>
        <linearGradient id={`${id}-anneau`} x1="14" y1="8" x2="52" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor={BLEU_CLAIR} />
          <stop offset="0.55" stopColor={BLEU} />
          <stop offset="1" stopColor={BLEU_FONCE} />
        </linearGradient>
        <linearGradient id={`${id}-onde`} x1="16" y1="30" x2="48" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor={CYAN} />
          <stop offset="0.5" stopColor="#a8f0ff" />
          <stop offset="1" stopColor={CYAN} />
        </linearGradient>
        <filter id={`${id}-halo`} x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="1.6" result="flou" />
          <feMerge>
            <feMergeNode in="flou" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Disque interieur : le signe porte son propre fond, il reste donc
          lisible aussi bien sur une surface claire que sombre. */}
      <circle cx="32" cy="29" r="20" fill={FOND} />

      {/* Queue de la bulle, tracee avant l'anneau pour que la jointure
          disparaisse sous le trait. */}
      <path
        d="M23.5 44.5C21 51 17.5 55.5 13 58.5C19.5 56 26 52.5 31 48.5Z"
        fill={`url(#${id}-anneau)`}
      />
      <circle
        cx="32"
        cy="29"
        r="20"
        stroke={`url(#${id}-anneau)`}
        strokeWidth="4.2"
        fill="none"
      />

      {/* Histogramme : la mesure, en retrait. */}
      <g fill={BLEU_CLAIR} opacity="0.45">
        <rect x="20.5" y="27" width="3.4" height="12" rx="1.5" />
        <rect x="26" y="20" width="3.4" height="19" rx="1.5" />
        <rect x="31.5" y="16" width="3.4" height="23" rx="1.5" />
        <rect x="37" y="23" width="3.4" height="16" rx="1.5" />
        <rect x="42.5" y="18.5" width="3.4" height="20.5" rx="1.5" />
      </g>

      {/* Onde : la voix, au premier plan. */}
      <path
        d="M15 29.5H20.5L23.5 21.5L26.5 37.5L29.5 15L33 42L36.5 22L39.5 32L42 27.5L44.5 29.5H49"
        stroke={`url(#${id}-onde)`}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        filter={`url(#${id}-halo)`}
      />
    </svg>
  );
}

/** Signe + nom, en option la signature. */
export default function Logo({
  size = 32,
  tagline = false,
  id = "dv-full",
  className = "",
}: {
  size?: number;
  tagline?: boolean;
  id?: string;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} id={id} />
      <span className="leading-none">
        <span
          className="font-black tracking-[-0.02em]"
          style={{ fontSize: size * 0.62 }}
        >
          <span className="text-slate-900 dark:text-white">Data</span>
          <span className="text-primary">Vox</span>
        </span>
        {tagline && (
          <span
            className="block text-slate-500 dark:text-slate-400 mt-1"
            style={{ fontSize: size * 0.24 }}
          >
            Natural Language Data Analysis
          </span>
        )}
      </span>
    </span>
  );
}
