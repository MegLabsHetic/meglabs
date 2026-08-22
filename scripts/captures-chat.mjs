/**
 * Capture la conversation en action : théâtre des agents, réponse, SQL déplié.
 *
 * Séparé de `captures.mjs` parce qu'il faut attendre de vrais appels au modèle, et
 * qu'une clé API est donc nécessaire. Lancé par scripts/captures.sh uniquement si
 * CHAT=1, pour que la passe habituelle reste gratuite et hors ligne.
 */
import { chromium } from "playwright";
import { mkdir, readFile } from "node:fs/promises";

const FRONT = process.env.FRONT ?? "http://frontend:3000";
const API = process.env.API ?? "http://backend:8000";
const API_PUBLIQUE = process.env.API_PUBLIQUE ?? "http://localhost:8000";
const SORTIE = process.env.SORTIE ?? "/captures";

const ENTETES_CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "*",
};

async function preparer(contexte) {
  // Redirection, et non relais : `route.fulfill` envoie un corps complet d'un seul
  // bloc, ce qui detruirait justement le streaming qu'on veut photographier. La
  // requete devient alors cross-origin, d'ou l'origine du service Docker ajoutee a
  // CORS_ORIGINS dans le .env local.
  await contexte.route(`${API_PUBLIQUE}/**`, (route) =>
    route.continue({ url: route.request().url().replace(API_PUBLIQUE, API) }),
  );
  await contexte.addInitScript(() => {
    const masquer = () => {
      const style = document.createElement("style");
      style.textContent = "nextjs-portal { display: none !important; }";
      document.head.append(style);
    };
    if (document.head) masquer();
    else document.addEventListener("DOMContentLoaded", masquer);
  });
}

async function semer(requete) {
  const espace = await requete.post(`${API}/api/workspaces`, {
    data: { nom: "Analyse RH — démonstration" },
  });
  const { id } = await espace.json();
  for (const nom of ["collaborateurs.csv", "transactions.csv"]) {
    await requete.post(`${API}/api/workspaces/${id}/files`, {
      multipart: {
        fichier: { name: nom, mimeType: "text/csv", buffer: await readFile(`/donnees/${nom}`) },
      },
    });
  }
  return id;
}

const navigateur = await chromium.launch();
const contexte = await navigateur.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 2,
  locale: "fr-FR",
  colorScheme: "dark",
  reducedMotion: "reduce",
});
await preparer(contexte);
await mkdir(SORTIE, { recursive: true });

const espaceId = await semer(contexte.request);
const page = await contexte.newPage();
await page.goto(`${FRONT}/`);
await page.evaluate((id) => localStorage.setItem("meglabs.espace", id), espaceId);
await page.goto(`${FRONT}/ia`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

console.log("Captures de la conversation :");

await page.getByRole("button", { name: "Quel est le salaire moyen par service ?" }).click();
// Le théâtre s'allume avant la réponse : c'est l'instant qu'on veut photographier.
await page.waitForTimeout(2200);
await page.screenshot({ path: `${SORTIE}/11-chat-agents.png` });
console.log(`  ${SORTIE}/11-chat-agents.png`);

// Le repli « appel(s) au modele » n'apparait qu'une fois l'evenement final recu :
// c'est le signal fiable que la reponse est complete.
await page.getByRole("button", { name: /appel\(s\) au modèle/ }).waitFor({ timeout: 120_000 });
await page.waitForTimeout(800);
await page.screenshot({ path: `${SORTIE}/12-chat-reponse.png` });
console.log(`  ${SORTIE}/12-chat-reponse.png`);

// Tout déplier : c'est la promesse de transparence, elle doit se voir sur l'image.
for (const libelle of [/Requête exécutée/, /Résultat détaillé/, /appel\(s\) au modèle/]) {
  const bouton = page.getByRole("button", { name: libelle }).first();
  if (await bouton.count()) await bouton.click();
}
await page.waitForTimeout(600);
await page.screenshot({ path: `${SORTIE}/13-chat-transparence.png`, fullPage: true });
console.log(`  ${SORTIE}/13-chat-transparence.png`);

// La démonstration de sécurité : le garde-fou refuse et propose autre chose.
await page.getByPlaceholder("Quel est le salaire moyen par service ?").fill(
  "Supprime toutes les lignes du fichier",
);
await page.getByRole("button", { name: "Demander" }).click();
await page.waitForTimeout(12_000);
await page.screenshot({ path: `${SORTIE}/14-chat-securite.png`, fullPage: true });
console.log(`  ${SORTIE}/14-chat-securite.png`);

await navigateur.close();
console.log("Terminé.");
