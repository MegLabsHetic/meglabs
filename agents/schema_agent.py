"""Agent de correspondance de schema : appele quand un fichier rafraichi
n'a plus exactement la structure de la source d'origine.

La comparaison mecanique (nom a nom) est faite avant, sans IA. L'agent
n'intervient que sur ce qu'elle ne sait pas trancher : « CA_HT » est-il
le nouveau nom de « chiffre_affaires » ? Sa proposition est toujours
soumise a l'utilisateur — jamais appliquee d'office.
"""

from agents.base_agent import BaseAgent
from agents.langue import directive
from agents.sql_agent import LANGUE_RULE
from config import AGENT_TEMPERATURES

SCHEMA_SYSTEM_PROMPT = LANGUE_RULE + """Tu compares la structure d'un fichier de donnees a celle
d'une table existante, pour decider si le fichier peut mettre a jour la table.

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "verdict": "compatible|incompatible",
  "explication": "2 a 3 phrases accessibles a un non-technicien",
  "renames": { "colonne_du_fichier": "colonne_de_la_table" },
  "ignorees": ["colonne du fichier sans equivalent"],
  "manquantes": ["colonne de la table absente du fichier"]
}

Regles STRICTES :
- "compatible" seulement si le fichier decrit VISIBLEMENT la meme chose que la
  table (memes entites, memes mesures), meme si des colonnes ont ete renommees,
  ajoutees ou reordonnees.
- "incompatible" si le fichier parle d'un autre sujet : dis-le clairement dans
  l'explication, en nommant ce que contient chaque cote.
- Ne propose un renommage que si les deux colonnes designent la MEME donnee.
  Dans le doute, laisse la colonne dans "ignorees" ou "manquantes".
- Les noms doivent etre repris EXACTEMENT tels que fournis.
- Reponds UNIQUEMENT en JSON valide."""


class SchemaAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SchemaMatcher",
            system_prompt=SCHEMA_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("profiler", 0.1),
        )

    def match(
        self,
        table: str,
        expected: list,
        incoming: list,
        samples: dict,
        langue: str = "fr",
    ) -> dict:
        # Aucune question a analyser ici : la langue est celle de l'interface,
        # transmise par l'appelant.
        self.reset()
        lines = [directive(langue), "", f"=== TABLE EXISTANTE \"{table}\" ==="]
        for col in expected:
            lines.append(f"  - {col['name']} : {col['type']}")

        lines.append("\n=== COLONNES DU FICHIER ENTRANT ===")
        for col in incoming:
            ex = samples.get(col, [])
            line = f"  - {col}"
            if ex:
                line += "  ex: " + ", ".join(str(v)[:30] for v in ex[:3])
            lines.append(line)

        return self.ask_json(
            "Ce fichier peut-il mettre a jour cette table ?", context="\n".join(lines)
        )
