"""Repository coding agent for isolated, reviewable idea attempts.

The model proposes complete file contents. This module validates every path and
applies those contents only inside the caller-provided temporary repository copy.
No generated code or test command is executed here.
"""

from __future__ import annotations

import difflib
from pathlib import Path, PurePosixPath

from agents.attempt_agent import FileChangeBatch, generate_changes
from schemas import ArchitectureCatalog, Idea, TechnicalPlan


class CodingAgent:
    """Generate and apply a bounded patch inside an isolated repository copy."""

    def __init__(self, model: str):
        self.model = model

    def generate_and_apply(
        self,
        *,
        root: Path,
        idea: Idea,
        plan: TechnicalPlan,
        catalog: ArchitectureCatalog,
        source_context: str,
    ) -> tuple[FileChangeBatch, str]:
        batch = generate_changes(
            idea, plan, catalog, source_context, self.model
        )
        paths = {PurePosixPath(change.path).as_posix() for change in batch.changes}
        if batch.changes and not any(
            path == "test_prototype.py" or path.endswith("/test_prototype.py")
            for path in paths
        ):
            raise RuntimeError("The coding agent did not generate test_prototype.py.")
        if plan.external_requirements and batch.changes and not any(
            "mock" in PurePosixPath(path).name.lower() for path in paths
        ):
            raise RuntimeError(
                "The plan has external requirements, but the coding agent did not "
                "generate a mock adapter."
            )
        return batch, self._apply(root, batch)

    @staticmethod
    def _apply(root: Path, batch: FileChangeBatch) -> str:
        root = root.resolve()
        diffs: list[str] = []
        total_bytes = 0
        for change in batch.changes:
            relative = PurePosixPath(change.path)
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                raise ValueError(f"Unsafe generated file path: {change.path}")
            if any(part.startswith(".") for part in relative.parts):
                raise ValueError(f"Generated changes cannot modify hidden files: {change.path}")
            if any(
                token in relative.name.lower()
                for token in ("credential", "secret", "private_key", "service-account")
            ) or relative.name.lower() in {"id_rsa", "id_ed25519"} or relative.name.lower().endswith(
                (".pem", ".key", ".p12", ".pfx")
            ):
                raise ValueError(f"Generated changes cannot modify credential files: {change.path}")

            candidate = root.joinpath(*relative.parts)
            if any(path.is_symlink() for path in (candidate, *candidate.parents) if path != root.parent):
                raise ValueError(f"Generated changes cannot follow repository symlinks: {change.path}")
            target = candidate.resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"Generated file escaped repository: {change.path}")
            before = target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
            after = change.content.splitlines(keepends=True)
            content_bytes = len(change.content.encode("utf-8"))
            total_bytes += content_bytes
            if content_bytes > 200_000 or total_bytes > 500_000:
                raise ValueError(f"Generated file is too large: {change.path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.content, encoding="utf-8")
            diffs.extend(difflib.unified_diff(
                before, after, fromfile=f"a/{relative.as_posix()}",
                tofile=f"b/{relative.as_posix()}",
            ))
            if sum(len(part.encode("utf-8")) for part in diffs) > 500_000:
                raise ValueError("Generated patch is too large to store safely.")
        return "".join(diffs)
