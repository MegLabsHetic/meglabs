"""Fournisseur Groq.

Mesure le 2026-08-11 sur `openai/gpt-oss-20b` et `openai/gpt-oss-120b` :

- `response_format={"type": "json_schema", ...}` rend du JSON conforme au schema.
- Le mode `json_object` seul ne suffit PAS : le modele produit du JSON valide avec
  ses propres noms de champs (`sql_query`, `query`…). Le contrat est faux alors que
  l'analyse syntaxique reussit — d'ou la validation systematique en aval.
- Forcer un outil echoue sur le 20b (« model did not call a tool »).
- Ce sont des modeles a raisonnement : la reponse est dans `content`, le raisonnement
  dans `reasoning`. Un budget de jetons trop court consomme tout le raisonnement et
  laisse `content` VIDE, sans erreur.
"""

from groq import AsyncGroq

from app.core.providers.base import ReponseBrute, Requete


class FournisseurGroq:
    nom = "groq"

    def __init__(self, cle: str) -> None:
        self._client = AsyncGroq(api_key=cle)

    async def repondre(self, requete: Requete) -> ReponseBrute:
        reponse = await self._client.chat.completions.create(
            model=requete.modele,
            max_tokens=requete.max_tokens,
            messages=[
                {"role": "system", "content": requete.instruction},
                {"role": "user", "content": requete.question},
            ],
            **self._options(requete),
        )

        choix = reponse.choices[0]
        message = choix.message
        return ReponseBrute(
            texte=(message.content or "").strip(),
            tokens_entree=reponse.usage.prompt_tokens,
            tokens_sortie=reponse.usage.completion_tokens,
            raison_arret=choix.finish_reason or "stop",
            raisonnement=(getattr(message, "reasoning", None) or "").strip(),
        )

    def _options(self, requete: Requete) -> dict:
        options: dict = {}
        if requete.schema is not None:
            options["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": requete.nom_schema,
                    "schema": requete.schema,
                    "strict": True,
                },
            }
        if requete.effort is not None:
            options["reasoning_effort"] = requete.effort
        return options
