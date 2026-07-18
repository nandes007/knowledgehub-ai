from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlmodel import Field


def utc_timestamp_field() -> Any:
    """A TIMESTAMPTZ column defaulting to now(), matching the section 4 DDL."""
    return Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
