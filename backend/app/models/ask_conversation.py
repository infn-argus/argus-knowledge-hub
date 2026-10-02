"""Ask ARGUS as a conversation: one person's questions in one workspace and the answers they got.

A follow-up ("and which of those are in AC1?") is answered with the earlier turns as context, so the
turns are kept. Each answer keeps the lookups it was built from, which are what make it checkable. A
conversation is its author's alone: the answers carry whatever that person was allowed to read.
"""
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class AskConversation(Base):
    __tablename__ = "ask_conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    owner: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AskMessage(Base):
    __tablename__ = "ask_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("ask_conversations.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String)                  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="")
    # An answer's lookups (tool, arguments, result, error, seconds), how it ended and how long it took.
    steps: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    stopped: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # answered | exhausted | failed | cancelled
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
