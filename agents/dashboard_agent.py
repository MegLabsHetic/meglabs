"""Agent d'edition de tableau de bord : pilote les widgets en langage naturel.

L'utilisateur dit « ajoute le panier moyen », « calcule plutot la marge hors
taxes », « enleve la courbe » — l'agent renvoie une operation structuree sur
les widgets. Rien n'est applique sans que le SQL produit ait ete execute avec
succes : un widget casse n'atteint jamais le tableau de bord.
"""

from agents.base_agent import BaseAgent
from agents.langue import directive, directive_pour
from agents.sql_agent import LANGUE_RULE, format_schema
from config import AGENT_TEMPERATURES

DASHBOARD_SYSTEM_PROMPT = LANGUE_RULE + """Tu edites un tableau de bord. On te donne le schema d'un
entrepot de donnees, la liste des indicateurs deja presents, et une demande de
l'utilisateur. Tu renvoies l'operation a appliquer.

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "reponse": "une phrase decrivant ce que tu as fait",
  "operations": [
    {
      "action": "add|update|remove",
      "widget_id": "id du widget existant (obligatoire pour update et remove)",
      "titre": "titre court de l'indicateur",
      "sql": "SELECT ... (obligatoire pour add et update)",
      "viz": "tuile|barres|barres_horizontales|courbe|anneau|table",
      "format": "nombre|pourcentage|monetaire",
      "style": {
        "couleur": "bleu|orange|aqua|jaune|magenta|vert|violet|rouge",
        "entourer": "max|min|extremes|aucun",
        "etiquettes": true
      }
    }
  ]
}

Regles STRICTES :
- SQL DuckDB valide, une SEULE instruction, SELECT (ou WITH ... SELECT) uniquement.
  Jamais de point-virgule, jamais d'ecriture.
- N'utilise QUE les tables et colonnes du schema fourni, avec leur nom EXACT.
- "tuile" : la requete renvoie UNE seule ligne et UNE seule colonne.
- "barres", "barres_horizontales", "anneau", "courbe" : la requete renvoie DEUX
  colonnes, le libelle puis la valeur, nommees AS libelle et AS valeur.
- Une evolution utilise date_trunc('month', colonne) et un tri par date croissante.
- Pour "update", reprends l'id exact du widget concerne et renvoie le SQL COMPLET
  corrige (pas un fragment).
- Pour "remove", seuls "action" et "widget_id" sont necessaires.

Apparence — "style" habille un indicateur SANS toucher au calcul :
- Une demande purement visuelle ("mets la courbe en orange", "entoure le pic",
  "affiche les valeurs") est un "update" avec SEULEMENT "widget_id" et "style".
  N'ecris PAS de SQL dans ce cas : le calcul ne change pas.
- "couleur" : uniquement un des huit noms de la liste. Ils suivent le theme
  clair ou sombre, ce qu'un code hexadecimal ne sait pas faire — ne propose un
  "#rrggbb" que si l'utilisateur donne lui-meme un code precis.
- "entourer" : "max" cercle le point le plus haut, "min" le plus bas,
  "extremes" les deux, "aucun" retire la mise en evidence.
  C'est la reponse a « entoure les pics », « montre le sommet », « marque le
  meilleur mois ».
- "etiquettes" : true affiche la valeur sur chaque marque.
- N'inclus "style" que si la demande porte dessus ; ne le renvoie jamais
  "par defaut" sur un ajout ordinaire.
- Si la demande est ambigue ou impossible avec ce schema, renvoie
  "operations": [] et explique pourquoi dans "reponse".
- Reponds UNIQUEMENT en JSON valide."""


class DashboardAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="DashboardEditor",
            system_prompt=DASHBOARD_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("kpi", 0.3),
        )

    def edit(
        self,
        schema: dict,
        widgets: list,
        message: str,
        history: list = None,
    ) -> dict:
        self.reset()
        context = directive_pour(message) + "\n\n" + format_schema(schema)
        context += "\n\n=== INDICATEURS ACTUELS DU TABLEAU DE BORD ==="
        if widgets:
            for w in widgets:
                context += (
                    f"\n- id={w.get('id')} | titre=\"{w.get('title')}\" "
                    f"| forme={w.get('viz')} | apparence={w.get('style') or 'par defaut'}"
                    f" | sql={w.get('sql')}"
                )
        else:
            context += "\n(aucun indicateur pour l'instant)"

        if history:
            context += "\n\n=== CONVERSATION PRECEDENTE ==="
            for m in history[-4:]:
                role = "Utilisateur" if m.get("role") == "user" else "Assistant"
                context += f"\n{role} : {str(m.get('content', ''))[:300]}"

        return self.ask_json(message, context=context)


PROPOSE_SYSTEM_PROMPT = LANGUE_RULE + """Tu es analyste. On te donne le schema d'un entrepot de donnees.
Tu proposes les indicateurs les plus utiles a suivre, chacun avec sa requete SQL.

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "kpis": [
    {
      "titre": "titre court",
      "description": "a quoi sert cet indicateur, en une phrase accessible",
      "sql": "SELECT ...",
      "viz": "tuile|barres|barres_horizontales|courbe|anneau|table",
      "format": "nombre|pourcentage|monetaire"
    }
  ]
}

Regles STRICTES :
- 6 a 9 indicateurs, du plus important au moins important.
- Commence par 3 ou 4 chiffres cles ("tuile"), puis les repartitions et l'evolution.
- SQL DuckDB valide, une SEULE instruction SELECT, sans point-virgule.
- N'utilise QUE les tables et colonnes du schema fourni, avec leur nom EXACT.
- "tuile" : UNE ligne, UNE colonne. Graphiques : DEUX colonnes nommees
  AS libelle et AS valeur, triees, limitees a 20 lignes.
- Une seule evolution temporelle, avec date_trunc('month', colonne).
- Reponds UNIQUEMENT en JSON valide."""


class KpiProposerAgent(BaseAgent):
    """Propose un premier tableau de bord a partir du seul schema de l'entrepot."""

    def __init__(self):
        super().__init__(
            name="KpiProposer",
            system_prompt=PROPOSE_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("kpi", 0.3),
        )

    def propose(
        self, schema: dict, dictionary: dict | None = None, langue: str = "fr"
    ) -> dict:
        # Ici il n'y a pas de question a analyser : la langue est celle de
        # l'interface, transmise par l'appelant.
        self.reset()
        return self.ask_json(
            "Propose les indicateurs a suivre pour ce jeu de donnees.",
            context=directive(langue) + "\n\n" + format_schema(schema, dictionary),
        )
