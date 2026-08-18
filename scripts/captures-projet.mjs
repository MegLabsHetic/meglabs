/**
 * Captures du déroulé du projet : historique Git, revues, intégration continue,
 * backlog. Le pendant des captures d'application, pour la partie du rapport qui
 * parle de la façon dont on a travaillé plutôt que du produit.
 *
 * Les pages GitHub sont photographiées déconnecté : le dépôt est public, ce que
 * voit le jury est donc exactement ce qui est capturé ici.
 *
 * Lancé par scripts/captures.sh, pas directement.
 */
import { chromium } from "playwright";
import { mkdir, readFile } from "node:fs/promises";

const DEPOT = process.env.DEPOT_GITHUB ?? "MegLabsHetic/meglabs";
const SORTIE = process.env.SORTIE_PROJET ?? "/captures/projet";
const GRAPHE = process.env.GRAPHE ?? "/entree/graphe.txt";

const PAGES = [
  ["depot", `https://github.com/${DEPOT}`, "Le dépôt"],
  ["historique", `https://github.com/${DEPOT}/commits/dev`, "L'historique de dev"],
  ["revues", `https://github.com/${DEPOT}/pulls?q=is%3Apr+sort%3Acreated-asc`, "Les revues"],
  ["integration-continue", `https://github.com/${DEPOT}/actions`, "L'intégration continue"],
  ["backlog", `https://github.com/${DEPOT}/issues?q=is%3Aissue`, "Le backlog"],
  ["tableau", "https://github.com/orgs/MegLabsHetic/projects/1", "Le tableau de suivi"],
  ["documentation", `https://github.com/${DEPOT}/wiki`, "La documentation"],
];

let rang = 0;

async function capturer(page, nom, { pleinePage = false } = {}) {
  rang += 1;
  const fichier = `${SORTIE}/${String(rang).padStart(2, "0")}-${nom}.png`;
  await page.screenshot({ path: fichier, fullPage: pleinePage });
  console.log(`  ${fichier}`);
}

/** Le graphe des branches, mis en page comme le terminal qui l'a produit. */
function pageGraphe(texte) {
  const echappe = texte.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  return `<!doctype html><meta charset="utf-8"><style>
    :root { color-scheme: dark; }
    body { margin: 0; background: #0a1211; }
    main { padding: 40px 44px; }
    h1 { margin: 0 0 4px; color: #f2f6f5; font: 600 20px/1.3 ui-sans-serif, system-ui, sans-serif; }
    p { margin: 0 0 28px; color: #9aaba8; font: 14px/1.5 ui-sans-serif, system-ui, sans-serif; }
    pre { margin: 0; color: #c3d0cd; font: 13px/1.75 ui-monospace, "Cascadia Code", Menlo, monospace;
          white-space: pre; tab-size: 2; }
  </style>
  <main>
    <h1>git log --graph --all --oneline --decorate</h1>
    <p>Une branche par lot de travail, partant de <code>dev</code> et y revenant par revue. Aucune branche n'est supprimée après fusion.</p>
    <pre>${echappe}</pre>
  </main>`;
}

const navigateur = await chromium.launch();
const contexte = await navigateur.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 2,
  locale: "fr-FR",
  colorScheme: "dark",
  reducedMotion: "reduce",
});

await mkdir(SORTIE, { recursive: true });
const page = await contexte.newPage();

console.log("Captures du projet :");

await page.setContent(pageGraphe(await readFile(GRAPHE, "utf8")));
await capturer(page, "graphe-des-branches", { pleinePage: true });

for (const [nom, url, quoi] of PAGES) {
  const reponse = await page.goto(url, { waitUntil: "domcontentloaded" });
  if (!reponse?.ok()) {
    console.log(`  (ignoré) ${quoi} : ${reponse?.status() ?? "injoignable"}`);
    continue;
  }
  // Le tableau de suivi est une application à part entière : elle se peint après
  // le chargement du document.
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1500);
  await capturer(page, nom);
}

await navigateur.close();
console.log("Terminé.");
