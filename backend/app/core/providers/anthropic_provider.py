"""Fournisseur Anthropic.

Deux particularites par rapport aux autres :

- **La sortie structuree passe par un outil force**, pas par un format de reponse. Le
  schema Pydantic devient le schema d'entree d'un outil que le modele est obligé
  d'appeler ; sa charge utile arrive deja analysee.
- **La mise en cache du prompt est explicite.** L'instruction systeme porte un marqueur
  `cache_control` : elle est stable d'un appel a l'autre, donc facturee une fois puis
  relue a un dixieme du prix. Attention, il existe un seuil minimal (de l'ordre du
  millier de jetons selon le modele) sous lequel rien n'est mis en cache, et cela
  echoue en silence : `tokens_caches` reste alors a zero, ce qui est la maniere de le
  detecter.

Non verifie en appel reel : le compte de l'equipe n'a pas de credit.
"""

import json

from anthropic import AsyncAnthropic

from app.core.providers.base import ReponseBrute, Requete


class FournisseurAnthropic:
    nom = "anthropic"

    def __init__(self, cle: str) -> None:
        self._client = AsyncAnthropic(api_key=cle)

    async def repondre(self, requete: Requete) -> ReponseBrute:
        reponse = await self._client.messages.create(
            model=requete.modele,
            max_tokens=requete.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": requete.instruction,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": requete.question}],
            **self._options(requete),
        )

        usage = reponse.usage
        return ReponseBrute(
            texte=self._extraire(reponse, requete),
            tokens_entree=usage.input_tokens,
            tokens_sortie=usage.output_tokens,
            tokens_caches=getattr(usage, "cache_read_input_tokens", 0) or 0,
            raison_arret=self._raison(reponse),
        )

    def _options(self, requete: Requete) -> dict:
        if requete.schema is None:
            return {}
        return {
            "tools": [
                {
                    "name": requete.nom_schema,
                    "description": "Retourne le resultat sous la forme attendue.",
                    "input_schema": requete.schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": requete.nom_schema},
        }

    def _extraire(self, reponse: object, requete: Requete) -> str:
        """Rend toujours du texte, pour que la validation en aval soit identique partout."""
        blocs = getattr(reponse, "content", []) or []
        if requete.schema is not None:
            for bloc in blocs:
                if getattr(bloc, "type", "") == "tool_use":
                    return json.dumps(bloc.input, ensure_ascii=False)
            return ""
        return "".join(bloc.text for bloc in blocs if getattr(bloc, "type", "") == "text").strip()

    def _raison(self, reponse: object) -> str:
        """Aligne le vocabulaire d'arret sur celui des autres fournisseurs."""
        brute = getattr(reponse, "stop_reason", None) or "stop"
        return "length" if brute == "max_tokens" else str(brute)
