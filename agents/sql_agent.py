"""Agent SQL : traduit une question en langage naturel en requete SQL DuckDB.

Meme principe fondateur que le reste de la plateforme : l'IA ne produit
jamais un chiffre, elle produit la *recette*. Ici la recette est du SQL,
execute par l'entrepot sur les vraies donnees. Le SQL est renvoye a
l'utilisateur pour rester auditable.
"""

from agents.base_agent import BaseAgent
from agents.langue import directive, directive_pour
from config import AGENT_TEMPERATURES

# Cette regle est placee en TETE de chaque prompt, pas en fin : le corps des
# consignes est redige en francais, et un modele suit la langue dominante de
# son instruction s'il n'a pas recu l'ordre contraire en premier.
LANGUE_RULE = """### REGLE N°1 — LANGUE DE REPONSE (prioritaire sur tout le reste)

Detecte la langue de la question de l'utilisateur et redige TOUS les textes
qui lui sont destines (reponse, titre, description, suggestions, explication)
dans CETTE langue, jamais dans une autre.

  Question en francais  -> tous les textes en francais.
  Question in English   -> ALL user-facing text in English. Not French.
  سؤال بالعربية          -> كل النصوص بالعربية.

Ces consignes sont ecrites en francais pour des raisons internes : cela ne
doit JAMAIS influencer la langue de ta reponse.

Le SQL, lui, ne change jamais : noms de tables et de colonnes exactement
comme dans le schema, quelle que soit la langue de la question.

---

"""

SQL_SYSTEM_PROMPT = LANGUE_RULE + """Tu es analyste de donnees. Tu traduis une question en langage naturel
en UNE requete SQL DuckDB executee sur un entrepot dont on te donne le schema.

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "reponse": "ta reponse, 2 a 4 phrases, ton accessible pour un non-technicien",
  "sql": "SELECT ... ou null si la question n'appelle aucun calcul",
  "titre": "titre court du resultat",
  "viz": "tuile|barres|barres_horizontales|courbe|anneau|table",
  "format": "nombre|pourcentage|monetaire",
  "suggestions": ["question de suivi 1", "question de suivi 2", "question de suivi 3"],
  "action": "rapport (UNIQUEMENT si l'utilisateur demande un rapport / compte rendu / bilan / document a envoyer), sinon null"
}

Regles STRICTES :
- SQL DuckDB valide, une SEULE instruction, SELECT (ou WITH ... SELECT) uniquement.
  Jamais INSERT/UPDATE/DELETE/CREATE/DROP/ATTACH/COPY, jamais de point-virgule.
- N'utilise QUE les tables et colonnes du schema fourni, avec leur nom EXACT.
- Deux colonnes maximum en sortie pour un graphique : le libelle puis la valeur.
  Nomme-les explicitement (AS libelle, AS valeur). Pour une tuile : une seule colonne.
- Trie et limite ce qui doit l'etre (ORDER BY ... LIMIT 20 pour une repartition).
- Pour une evolution : agrege par periode avec date_trunc('month', colonne) et
  trie par date croissante.
- Les valeurs d'exemple du schema te donnent les modalites reelles : utilise-les
  telles quelles, ne devine pas la casse ni les accents.
- Si la question ne demande aucun calcul (bonjour, aide...), mets "sql": null.
- Si l'utilisateur reclame un RAPPORT (« fais-moi un rapport », « a report in PDF »,
  « تقرير »), mets "action": "rapport", "sql": null, et annonce dans "reponse"
  que le rapport va etre prepare. Sinon "action": null.
- 3 suggestions maximum, courtes, reellement repondables avec ce schema.
- Reponds UNIQUEMENT en JSON valide."""


def format_schema(schema: dict, dictionary: dict | None = None) -> str:
    """Met le schema de l'entrepot en forme pour le contexte du modele.

    Le libelle d'origine est fourni a cote de l'identifiant SQL : c'est lui
    qui porte le sens quand le fichier n'est pas en caracteres latins
    (« almbyaat » ne veut rien dire, « المبيعات » si).
    """
    lines = ["=== SCHEMA DE L'ENTREPOT ==="]
    for table in schema.get("tables", []):
        lines.append(f"\nTable \"{table['name']}\" ({table.get('rows', 0)} lignes)")
        for col in table.get("columns", []):
            line = f"  - {col['name']} : {col['type']}"
            if col.get("label"):
                line += f"  (intitule d'origine : « {col['label']} »)"
            samples = col.get("samples") or []
            if samples:
                line += "  ex: " + ", ".join(str(s)[:30] for s in samples[:3])
            lines.append(line)
    if not schema.get("tables"):
        lines.append("(entrepot vide)")

    if dictionary:
        lines.append("\n=== DEFINITIONS METIER ===")
        for name, desc in list(dictionary.items())[:40]:
            lines.append(f"  - {name} : {desc}")
    return "\n".join(lines)


class SQLAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SQLAnalyst",
            system_prompt=SQL_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("orchestrator", 0.3),
        )

    def answer(
        self,
        schema: dict,
        message: str,
        history: list = None,
        dictionary: dict | None = None,
    ) -> dict:
        # Stateless : l'agent est partage entre tous les tenants, on repart
        # systematiquement de zero et on injecte l'historique dans le contexte.
        self.reset()
        # La langue est tranchee en code et imposee en tete de contexte : une
        # question anglaise perdue dans un contexte francais serait sinon
        # traitee en francais.
        context = directive_pour(message) + "\n\n" + format_schema(schema, dictionary)
        if history:
            context += "\n\n=== CONVERSATION PRECEDENTE ==="
            for m in history[-6:]:
                role = "Utilisateur" if m.get("role") == "user" else "Assistant"
                context += f"\n{role} : {str(m.get('content', ''))[:300]}"
        return self.ask_json(message, context=context)

    def repair(self, schema: dict, sql: str, error: str, message: str) -> dict:
        """Deuxieme chance apres une erreur SQL : on renvoie l'erreur au modele.

        Une requete refusee par DuckDB (colonne mal orthographiee, fonction
        inconnue) est presque toujours rattrapable — sans quoi l'utilisateur
        recoit une erreur technique qui ne lui apprend rien.
        """
        self.reset()
        context = (
            directive_pour(message)
            + "\n\n"
            + format_schema(schema)
            + f"\n\n=== REQUETE REFUSEE ===\n{sql}\n\n=== ERREUR DUCKDB ===\n{error}"
        )
        return self.ask_json(
            f"Corrige la requete pour repondre a : {message}", context=context
        )
