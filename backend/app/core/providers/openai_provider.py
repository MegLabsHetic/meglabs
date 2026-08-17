"""Fournisseur OpenAI.

Non verifie en appel reel : le compte de l'equipe n'a pas de credit. Le schema de
requete suit la documentation officielle du catalogue GPT-5.6, et un test marque
`integration` le confirmera des qu'une cle sera disponible.
"""

from openai import AsyncOpenAI

from app.core.providers.base import ReponseBrute, Requete


class FournisseurOpenAI:
    nom = "openai"

    def __init__(self, cle: str) -> None:
        self._client = AsyncOpenAI(api_key=cle)

    async def repondre(self, requete: Requete) -> ReponseBrute:
        reponse = await self._client.chat.completions.create(
            model=requete.modele,
            max_completion_tokens=requete.max_tokens,
            messages=[
                {"role": "system", "content": requete.instruction},
                {"role": "user", "content": requete.question},
            ],
            **self._options(requete),
        )

        choix = reponse.choices[0]
        usage = reponse.usage
        return ReponseBrute(
            texte=(choix.message.content or "").strip(),
            tokens_entree=usage.prompt_tokens if usage else 0,
            tokens_sortie=usage.completion_tokens if usage else 0,
            tokens_caches=self._tokens_caches(usage),
            raison_arret=choix.finish_reason or "stop",
        )

    def _options(self, requete: Requete) -> dict:
        if requete.schema is None:
            return {}
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": requete.nom_schema,
                    "schema": requete.schema,
                    "strict": True,
                },
            }
        }

    def _tokens_caches(self, usage: object | None) -> int:
        details = getattr(usage, "prompt_tokens_details", None)
        return int(getattr(details, "cached_tokens", 0) or 0)
