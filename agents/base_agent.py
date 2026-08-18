import json
import logging
import os

import anthropic

from config import CLAUDE_MAX_TOKENS, CLAUDE_MODEL

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all AI agents. Handles Claude API communication."""

    def __init__(self, name: str, system_prompt: str, temperature: float = 0.2):
        self.name = name
        self.system_prompt = system_prompt
        self.temperature = temperature
        self._client = None
        self._api_key = None
        self.history = []

    @property
    def client(self):
        """Lazily create/refresh the Anthropic client when the API key changes."""
        current_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if self._client is None or self._api_key != current_key:
            if not current_key:
                self._client = None
                self._api_key = ""
                return None
            self._client = anthropic.Anthropic(api_key=current_key)
            self._api_key = current_key
        return self._client

    def ask(self, user_message: str, context: str = "") -> str:
        """Send a message to Claude and get a response."""
        current_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not current_key:
            return (
                f"[Agent {self.name}] Cle API Anthropic non configuree. "
                "Entrez votre cle dans les parametres."
            )

        full_message = user_message
        if context:
            full_message = f"[CONTEXTE DONNEES]\n{context}\n\n[REQUETE]\n{user_message}"

        # Chaque appel repart de zero. Les agents sont des singletons partages
        # entre tous les utilisateurs (service engine sans etat) : conserver
        # l'historique ferait fuiter le contexte d'un utilisateur dans la
        # requete du suivant. Le multi-tour passe toujours par `context`.
        self.history = [{"role": "user", "content": full_message}]
        messages = self.history

        try:
            # Note: pas de parametre temperature — les modeles Claude recents
            # (Sonnet 5+) rejettent les parametres d'echantillonnage non-defaut.
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=self.system_prompt,
                messages=messages,
            )
            # Les modeles recents (Sonnet 5+) peuvent renvoyer un bloc de reflexion
            # (thinking) avant le texte : on prend le premier bloc de type "text",
            # pas forcement content[0].
            reply = next(
                (
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text"
                ),
                "",
            )
            self.history.append({"role": "assistant", "content": reply})
            return reply

        except anthropic.AuthenticationError:
            logger.error("Agent %s: Authentication error", self.name)
            return f"[Agent {self.name}] Cle API invalide. Verifiez votre cle Anthropic."

        except anthropic.RateLimitError:
            logger.warning("Agent %s: Rate limit reached", self.name)
            return (
                f"[Agent {self.name}] Limite de requetes atteinte. "
                "Reessayez dans quelques secondes."
            )

        except anthropic.APIConnectionError:
            logger.error("Agent %s: Connection error", self.name)
            return (
                f"[Agent {self.name}] Erreur de connexion a l'API. "
                "Verifiez votre connexion internet."
            )

        except Exception as e:
            logger.error("Agent %s error: %s", self.name, str(e))
            return f"[Agent {self.name}] Erreur: {str(e)}"

    def ask_json(self, user_message: str, context: str = "") -> dict:
        """Send a message and parse the response as JSON."""
        raw = self.ask(user_message, context)

        # Check for error messages
        if raw.startswith("[Agent"):
            return {"error": raw, "raw_response": raw}

        text = raw.strip()

        # Extract JSON from markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

            # Try to find JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end > start:
                try:
                    return {"items": json.loads(text[start:end])}
                except json.JSONDecodeError:
                    pass

            logger.warning("Agent %s: Could not parse JSON from response", self.name)
            return {"raw_response": raw, "error": "Could not parse JSON"}

    def reset(self):
        """Reset conversation history."""
        self.history = []
