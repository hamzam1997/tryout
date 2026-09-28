"""SQLAlchemy 2.0 ORM database models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from schemas import (
    AttemptStatus,
    IdeaStatus,
    MeetingSource,
    MeetingStatus,
    RepoSource,
)


class UTCDateTime(TypeDecorator):
    """A DateTime that round-trips as timezone-aware UTC.

    SQLite has no native datetime type and silently discards tzinfo, so an
    aware value written through a plain DateTime comes back naive.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    """Declarative base class for all database models."""
    pass


class Repository(Base):
    """A codebase the agent can attempt ideas against."""

    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Clone URL or filesystem path. Unique so re-onboarding finds the existing row.
    source: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String, nullable=False, default=RepoSource.LOCAL.value
    )
    # Commit the cached catalog was built from; drives cache invalidation.
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    catalog_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalog_generated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class Meeting(Base):
    """An ingested meeting transcript and the minutes derived from it."""

    __tablename__ = "meeting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # When the meeting happened, not when it was ingested. Null when the
    # source cannot supply it, e.g. a pasted transcript.
    occurred_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    external_source: Mapped[str] = mapped_column(
        String, nullable=False, default=MeetingSource.PASTE.value
    )
    # The source system's own id; guards against re-ingesting a recording.
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Speaker-attributed text with cue times preserved for the extractor.
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    minutes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Explicit so a failed extraction is distinguishable from one not yet run.
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=MeetingStatus.PENDING.value, index=True
    )
    # Idea extraction is best-effort after minutes; persist the last failure.
    ideas_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    ideas: Mapped[list["Idea"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class Idea(Base):
    """A catalog-grounded proposal extracted from a meeting, awaiting human approval."""

    __tablename__ = "idea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Verbatim quote, kept for auditability.
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    speaker: Mapped[str] = mapped_column(String, nullable=False, default="")
    # Offset into the transcript ("00:12:30"), not a wall-clock time.
    cue_time: Mapped[str] = mapped_column(String, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="")
    attempt_hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # JSON list of catalog modules/routes/models/integrations this idea would touch.
    catalog_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Stable key linking the same proposal across meetings.
    idea_key: Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    # The earliest idea sharing this idea_key; null if original.
    original_idea_id: Mapped[int | None] = mapped_column(
        ForeignKey("idea.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=IdeaStatus.PENDING.value, index=True
    )
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    meeting: Mapped["Meeting"] = relationship(back_populates="ideas")
    original_idea: Mapped["Idea | None"] = relationship(
        remote_side=[id], foreign_keys=[original_idea_id]
    )
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )


class Attempt(Base):
    """One run of the agent trying to build an approved idea in a repo."""

    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(
        ForeignKey("idea.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE"), nullable=False
    )
    # Commit the ephemeral working copy started from.
    repo_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=AttemptStatus.QUEUED.value
    )
    plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    test_stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set once on the first move out of QUEUED; with finished_at, the duration
    # charged against the idea's compute budget.
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    idea: Mapped["Idea"] = relationship(back_populates="attempts")
    repository: Mapped["Repository"] = relationship(back_populates="attempts")
    friction_logs: Mapped[list["FrictionLog"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class FrictionLog(Base):
    """One blocker the agent hit, and who owns unblocking it."""

    __tablename__ = "friction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # category, service_name and owning_team are indexed because the
    # bottleneck map aggregates across all attempts by each of them.
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    owning_team: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    # Path to the stub the agent wrote to get past this blocker.
    mock_implementation_path: Mapped[str] = mapped_column(
        String, nullable=False, default=""
    )
    required_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    readiness_checklist_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    attempt: Mapped["Attempt"] = relationship(back_populates="friction_logs")


# Model aliases for compatibility
RepositoryModel = Repository
MeetingModel = Meeting
IdeaModel = Idea
AttemptModel = Attempt
FrictionLogModel = FrictionLog
