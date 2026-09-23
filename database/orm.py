"""SQLAlchemy 2.0 declarative ORM models."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from database.models import (
    AttemptStatus,
    IdeaStatus,
    MeetingSource,
    RepoSource,
)


class Base(DeclarativeBase):
    """Declarative base class for all database models."""
    pass


class RepositoryModel(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String, nullable=False, default=RepoSource.LOCAL.value
    )
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    catalog_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalog_generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    attempts: Mapped[list["AttemptModel"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class MeetingModel(Base):
    __tablename__ = "meeting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[str | None] = mapped_column(String, nullable=True)
    external_source: Mapped[str] = mapped_column(
        String, nullable=False, default=MeetingSource.PASTE.value
    )
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    minutes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    ideas: Mapped[list["IdeaModel"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class IdeaModel(Base):
    __tablename__ = "idea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    speaker: Mapped[str] = mapped_column(String, nullable=False, default="")
    timestamp: Mapped[str] = mapped_column(String, nullable=False, default="")
    urgency: Mapped[str] = mapped_column(String, nullable=False, default="")
    feasibility_hypothesis: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    fingerprint: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("idea.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=IdeaStatus.PENDING.value, index=True
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    meeting: Mapped["MeetingModel"] = relationship(back_populates="ideas")
    duplicate_of: Mapped["IdeaModel | None"] = relationship(
        remote_side=[id], foreign_keys=[duplicate_of_id]
    )
    attempts: Mapped[list["AttemptModel"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )


class AttemptModel(Base):
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(
        ForeignKey("idea.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE"), nullable=False
    )
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
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    idea: Mapped["IdeaModel"] = relationship(back_populates="attempts")
    repository: Mapped["RepositoryModel"] = relationship(back_populates="attempts")
    friction_logs: Mapped[list["FrictionLogModel"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class FrictionLogModel(Base):
    __tablename__ = "friction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    owning_team: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    mock_implementation_path: Mapped[str] = mapped_column(
        String, nullable=False, default=""
    )
    required_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    readiness_checklist_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    attempt: Mapped["AttemptModel"] = relationship(back_populates="friction_logs")
