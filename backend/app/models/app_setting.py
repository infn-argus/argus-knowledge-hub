from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class AppSetting(Base, TimestampMixin):
    """Installation-wide administration settings.

    Deliberately not workspace-scoped and deliberately key/value: these are
    the handful of decisions that apply to the whole installation, and the
    set of them grows by one every few months. A column per setting would
    mean a migration per decision.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
