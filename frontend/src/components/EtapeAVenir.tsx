/**
 * Étape du parcours pas encore livrée.
 *
 * On dit ce qui viendra et quand, plutôt que de montrer une maquette. Une interface
 * qui fait semblant coûte la confiance du jury dès qu'il clique.
 */
import Link from "next/link";

export function EtapeAVenir({
  titre,
  resume,
  attendu,
  contenu,
}: {
  titre: string;
  resume: string;
  attendu: string;
  contenu: string[];
}) {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <p className="text-xs uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>
        Prévu pour le {attendu}
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{titre}</h1>
      <p className="mt-2" style={{ color: "var(--ink-2)" }}>
        {resume}
      </p>

      <div
        className="mt-6 rounded-xl border p-5"
        style={{ background: "var(--surface-1)", borderColor: "var(--bordure)" }}
      >
        <h2 className="text-sm font-medium">Ce que cette étape apportera</h2>
        <ul className="mt-3 space-y-2 text-sm" style={{ color: "var(--ink-2)" }}>
          {contenu.map((ligne) => (
            <li key={ligne} className="flex gap-2.5">
              <span aria-hidden style={{ color: "var(--ink-muted)" }}>
                —
              </span>
              <span>{ligne}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-6 text-sm" style={{ color: "var(--ink-2)" }}>
        En attendant,{" "}
        <Link href="/exploration" className="underline underline-offset-2">
          l&apos;exploration d&apos;un fichier
        </Link>{" "}
        fonctionne déjà de bout en bout.
      </p>
    </main>
  );
}
