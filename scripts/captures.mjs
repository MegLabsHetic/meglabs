/**
 * Captures d'écran de l'application, pour le rapport et la soutenance.
 *
 * Tourne dans l'image officielle Playwright plutôt qu'en local : elle embarque les
 * navigateurs, et rien n'est ajouté aux dépendances du projet. L'application est
 * jointe par le réseau Docker, donc sous ses noms de service.
 *
 * Usage, depuis la racine du dépôt et avec la pile démarrée :
 *   ./scripts/captures.sh
 */
import { chromium } from "playwright";
import { mkdir, readFile } from "node:fs/promises";

const FRONT = process.env.FRONT ?? "http://frontend:3000";
const API = process.env.API ?? "http://backend:8000";
// L'adresse que le navigateur de l'utilisateur utiliserait. Depuis le conteneur,
// elle ne mène nulle part : voir preparer().
const API_PUBLIQUE = process.env.API_PUBLIQUE ?? "http://localhost:8000";
const SORTIE = process.env.SORTIE ?? "/captures";
const LARGEUR = 1440;

/**
 * Rend un contexte utilisable pour la photo.
 *
 * Deux ajustements, tous deux dus au fait qu'on photographie une pile de
 * développement depuis un conteneur :
 *  - le bundle front porte l'adresse publique du backend, injectée au build ; dans
 *    ce réseau elle ne résout pas. On relaie donc l'appel depuis le script plutôt
 *    que de le rediriger : une redirection le rendrait cross-origin et le backend
 *    le refuserait, sa liste d'origines autorisées ne connaissant pas les noms de
 *    services Docker. Relayer évite d'ajouter une origine de confiance au seul
 *    profit d'un script de capture ;
 *  - Next affiche en développement une pastille flottante qui n'a rien à faire sur
 *    une capture destinée à un rapport.
 */
const ENTETES_CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "*",
};

async function preparer(contexte) {
  await contexte.route(`${API_PUBLIQUE}/**`, async (route) => {
    const demande = route.request();
    if (demande.method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: ENTETES_CORS });
    }
    const reponse = await contexte.request.fetch(demande.url().replace(API_PUBLIQUE, API), {
      method: demande.method(),
      headers: demande.headers(),
      data: demande.postDataBuffer() ?? undefined,
    });
    // Le corps est déjà décodé : conserver ces en-têtes ferait mentir la réponse.
    const { "content-encoding": _e, "content-length": _l, ...entetes } = reponse.headers();
    await route.fulfill({
      status: reponse.status(),
      headers: { ...entetes, ...ENTETES_CORS },
      body: await reponse.body(),
    });
  });
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

/** Une capture attendue qui ne part pas est un bug du script, pas un détail. */
async function exiger(cible, description) {
  if (!(await cible.count())) {
    throw new Error(`Élément introuvable pour la capture : ${description}`);
  }
  return cible;
}

/** Sert de repère de nommage : les fichiers se lisent dans l'ordre du parcours. */
let rang = 0;

async function capturer(page, nom, { pleinePage = true } = {}) {
  rang += 1;
  const fichier = `${SORTIE}/${String(rang).padStart(2, "0")}-${nom}.png`;
  // La révélation au défilement est déclenchée par l'observateur : sans un passage
  // en bas de page, les sections basses seraient photographiées vides.
  if (pleinePage) {
    await page.evaluate(async () => {
      await new Promise((fin) => {
        let position = 0;
        const pas = () => {
          position += window.innerHeight * 0.8;
          window.scrollTo(0, position);
          if (position < document.body.scrollHeight) setTimeout(pas, 120);
          else setTimeout(() => (window.scrollTo(0, 0), fin()), 400);
        };
        pas();
      });
    });
    await page.waitForTimeout(700);
  }
  await page.screenshot({ path: fichier, fullPage: pleinePage });
  console.log(`  ${fichier}`);
}

async function verifier(reponse, quoi) {
  if (!reponse.ok()) {
    throw new Error(`${quoi} : ${reponse.status()} ${await reponse.text()}`);
  }
  return reponse;
}

async function semer(requete) {
  const espace = await verifier(
    await requete.post(`${API}/api/workspaces`, {
      data: { nom: "Analyse RH — démonstration" },
    }),
    "création de l'espace",
  );
  const { id } = await espace.json();

  const depots = {};
  for (const nom of ["collaborateurs.csv", "transactions.csv"]) {
    const contenu = await readFile(`/donnees/${nom}`);
    const depose = await verifier(
      await requete.post(`${API}/api/workspaces/${id}/files`, {
        multipart: { fichier: { name: nom, mimeType: "text/csv", buffer: contenu } },
      }),
      `dépôt de ${nom}`,
    );
    depots[nom] = (await depose.json()).fichier.id;
  }
  // Le fichier RH porte les salaires et les données personnelles : c'est celui
  // qu'on montre, pas celui que l'application choisirait par défaut.
  return { id, fichierId: depots["collaborateurs.csv"] };
}

const navigateur = await chromium.launch();
const contexte = await navigateur.newContext({
  viewport: { width: LARGEUR, height: 900 },
  deviceScaleFactor: 2,
  locale: "fr-FR",
  colorScheme: "dark",
  // Les animations d'entrée sont belles à l'écran et floues en photo : on les fige.
  reducedMotion: "reduce",
});

await preparer(contexte);
await mkdir(SORTIE, { recursive: true });
const { id: espaceId, fichierId } = await semer(contexte.request);
const page = await contexte.newPage();

console.log("Captures :");

await page.goto(`${FRONT}/`, { waitUntil: "networkidle" });
await capturer(page, "accueil");

// L'atelier retient l'espace et le fichier courants côté navigateur : on les pose
// avant d'entrer, comme le ferait quelqu'un qui revient sur son travail.
await page.evaluate(
  ([espace, fichier]) => {
    localStorage.setItem("meglabs.espace", espace);
    localStorage.setItem("meglabs.fichier", fichier);
  },
  [espaceId, fichierId],
);

await page.goto(`${FRONT}/donnees`, { waitUntil: "networkidle" });
await page.waitForTimeout(900);
await capturer(page, "donnees");

await page.goto(`${FRONT}/exploration`, { waitUntil: "networkidle" });
await page.waitForTimeout(1400);
await capturer(page, "exploration-profil");

// Le détail d'une colonne : on ouvre celle qui porte les valeurs aberrantes.
const ligne = await exiger(
  page.locator("tr", { hasText: "salaire_annuel" }).first(),
  "ligne de la colonne salaire_annuel",
);
await ligne.click();
await page.waitForTimeout(600);
await capturer(page, "colonne-detail");

const filtre = await exiger(
  page.getByRole("button", { name: /À corriger/ }),
  "filtre « À corriger »",
);
await filtre.click();
await page.waitForTimeout(400);
await capturer(page, "colonnes-a-corriger");
await filtre.click();

const bouton = await exiger(
  // « exact », sinon la carte du fichier marquée « À pseudonymiser » répond aussi.
  page.getByRole("button", { name: "Pseudonymiser", exact: true }),
  "bouton « Pseudonymiser »",
);
await bouton.click();
await page.waitForTimeout(3500);
await capturer(page, "pseudonymise");

for (const [chemin, nom] of [
  ["/dashboard", "etape-tableau-de-bord"],
  ["/ia", "etape-ia"],
  ["/rapport", "etape-rapport"],
]) {
  await page.goto(`${FRONT}${chemin}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await capturer(page, nom);
}

// Une vue mobile : c'est la première question d'un jury sur une interface web.
const mobile = await navigateur.newContext({
  viewport: { width: 414, height: 896 },
  deviceScaleFactor: 3,
  locale: "fr-FR",
  colorScheme: "dark",
  reducedMotion: "reduce",
  isMobile: true,
  hasTouch: true,
});
await preparer(mobile);
const petit = await mobile.newPage();
await petit.goto(`${FRONT}/`, { waitUntil: "networkidle" });
// Le premier écran seulement : déroulée en entier, la page fait quinze mille pixels
// de haut et n'est plus lisible une fois posée dans un rapport.
await capturer(petit, "accueil-mobile", { pleinePage: false });

await navigateur.close();
console.log("Terminé.");
