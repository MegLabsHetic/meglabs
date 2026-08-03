"""Message d'une conversation, avec la trace de ce qui l'a produit."""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class ChatMessage(Entity):
    __tablename__ = "chat_messages"

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)

    # Le SQL est conserve pour deux raisons : le montrer a l'utilisateur, et le
    # rejouer tel quel dans le notebook exporte.
    sql_executed: Mapped[str | None] = mapped_column(Text, default=None)
    agent_trace: Mapped[dict | None] = mapped_column(JSON, default=None)
    cost_cents: Mapped[float] = mapped_column(default=0.0)
    cached: Mapped[bool] = mapped_column(default=False)
