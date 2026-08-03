"""Journal des appels LLM : la source de verite du cout affiche a l'utilisateur."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class LlmCallLog(Entity):
    __tablename__ = "llm_call_logs"

    agent: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(100))

    tokens_in: Mapped[int] = mapped_column(default=0)
    tokens_out: Mapped[int] = mapped_column(default=0)
    # Tokens servis par le cache du fournisseur : c'est l'economie realisee, donc la
    # quantite a mettre en avant.
    cached_tokens: Mapped[int] = mapped_column(default=0)

    cost_cents: Mapped[float] = mapped_column(default=0.0)
    duration_ms: Mapped[int] = mapped_column(default=0)

    # Reste nul tant que les facteurs d'emission ne sont pas sources et dates. Afficher
    # une estimation non sourcee serait de l'ecoblanchiment, pas un argument.
    co2e_mg: Mapped[float | None] = mapped_column(default=None)
