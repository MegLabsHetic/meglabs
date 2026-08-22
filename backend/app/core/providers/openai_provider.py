"""Fournisseur OpenAI.

Non verifie en appel reel : le compte de l'equipe n'a pas de credit. Le schema de
requete suit la documentation officielle du catalogue GPT-5.6, et un test marque
`integration` le confirmera des qu'une cle sera disponible.
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.providers.base import Fragment, ReponseBrute, Requete, adapter_strict


class FournisseurOpenAI:
    """Client OpenAI, ou tout service qui en expose l'interface.

    Scaleway sert le meme modele ouvert derriere la meme API : plutot qu'une classe
    de plus, on change l'adresse. Le nom reste distinct pour que la trace dise chez
    qui l'appel est reellement parti.
    """

    def __init__(self, cle: str, base_url: str | None = None, nom: str = "openai") -> None:
        self.nom = nom
        self._client = AsyncOpenAI(api_key=cle, base_url=base_url)

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

    async def diffuser(self, requete: Requete) -> AsyncIterator[Fragment]:
        flux = await self._client.chat.completions.create(
            model=requete.modele,
            max_completion_tokens=requete.max_tokens,
            messages=[
                {"role": "system", "content": requete.instruction},
                {"role": "user", "content": requete.question},
            ],
            stream=True,
            stream_options={"include_usage": True},
            **self._options(requete),
        )

        morceaux: list[str] = []
        usage = None
        raison = "stop"
        async for evenement in flux:
            usage = getattr(evenement, "usage", None) or usage
            for choix in evenement.choices:
                raison = choix.finish_reason or raison
                texte = choix.delta.content or ""
                if texte:
                    morceaux.append(texte)
                    yield Fragment(texte=texte)

        yield Fragment(
            fin=ReponseBrute(
                texte="".join(morceaux).strip(),
                tokens_entree=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_sortie=getattr(usage, "completion_tokens", 0) or 0,
                tokens_caches=self._tokens_caches(usage),
                raison_arret=raison,
            )
        )

    def _options(self, requete: Requete) -> dict:
        if requete.schema is None:
            return {}
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": requete.nom_schema,
                    "schema": adapter_strict(requete.schema),
                    "strict": True,
                },
            }
        }

    def _tokens_caches(self, usage: object | None) -> int:
        details = getattr(usage, "prompt_tokens_details", None)
        return int(getattr(details, "cached_tokens", 0) or 0)
