"""Cache de reponses : meme question sur les memes donnees, cout nul.

La cle est l'empreinte de la question normalisee et du jeu de donnees, pas la question
brute : « Quel est le CA ? » et « quel est le ca ? » doivent tomber sur la meme entree.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class QueryCache(Base):
    __tablename__ = "query_cache"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
