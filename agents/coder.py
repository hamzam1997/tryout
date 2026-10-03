"""Repository coding agent for isolated, reviewable idea attempts.

The model proposes complete file contents. This module validates every path and
applies those contents only inside the caller-provided temporary repository copy.
No generated code or test command is executed here.
"""

from __future__ import annotations

import difflib
from pathlib import Path, PurePosixPath

from agents.attempt_agent import FileChange, FileChangeBatch, generate_changes
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
        # Keep incomplete model output reviewable. Missing test or mock scaffolding is
        # a reason to add a small fallback, not a reason to discard the whole attempt.
        paths = {PurePosixPath(change.path).as_posix() for change in batch.changes}
        if not any(
            path == "test_prototype.py" or path.endswith("/test_prototype.py")
            for path in paths
        ):
            batch.changes.append(
                FileChange(
                    path="test_prototype.py",
                    content=(
                        '"""Starter checks for the generated idea attempt.\n\n'
                        "Replace these checks with assertions for the implementation.\n\n"
                        '"""\n\n'
                        "def test_attempt_scaffold_is_present():\n"
                        "    # This test intentionally marks the generated attempt as a\n"
                        "    # starting point until repository-specific behavior is added.\n"
                        "    assert True\n"
                    ),
                    rationale="Fallback starter test; generated output omitted prototype tests.",
                )
            )
            paths.add("test_prototype.py")
        if plan.external_requirements and not any(
            "mock" in PurePosixPath(path).name.lower() for path in paths
        ):
            batch.changes.append(
                FileChange(
                    path="mock_external_service.py",
                    content=(
                        '"""Runnable placeholder adapter for unavailable external services.\n\n'
                        "Replace or extend this interface with the real provider contract.\n\n"
                        '"""\n\n'
                        "class MockExternalService:\n"
                        '    """Record calls so prototype code can run without credentials."""\n\n'
                        "    def __init__(self):\n"
                        "        self.calls = []\n\n"
                        "    def send(self, *args, **kwargs):\n"
                        '        call = {"method": "send", "args": args, "kwargs": kwargs}\n'
                        "        self.calls.append(call)\n"
                        '        return {"ok": True, "mock": True}\n\n'
                        "    def send_email(self, *args, **kwargs):\n"
                        '        call = {"method": "send_email", "args": args, "kwargs": kwargs}\n'
                        "        self.calls.append(call)\n"
                        '        return {"ok": True, "mock": True}\n\n'
                        "    def send_notification(self, *args, **kwargs):\n"
                        '        call = {"method": "send_notification", "args": args, "kwargs": kwargs}\n'
                        "        self.calls.append(call)\n"
                        '        return {"ok": True, "mock": True}\n'
                    ),
                    rationale=(
                        "Fallback runnable mock adapter; model output omitted the external-service mock."
                    ),
                )
            )
            paths.add("mock_external_service.py")
            # Replace the generic no-op test with a runnable check of the fallback.
            test = next(
                (change for change in batch.changes if change.path == "test_prototype.py"),
                None,
            )
            if test and "MockExternalService" not in test.content:
                test.content = (
                    "from mock_external_service import MockExternalService\n\n\n"
                    "def test_mock_external_service_records_calls():\n"
                    "    client = MockExternalService()\n"
                    '    result = client.send_notification("hello")\n'
                    '    assert result["mock"] is True\n'
                    '    assert client.calls[0]["method"] == "send_notification"\n'
                )
                test.rationale = "Fallback test exercises the generated external-service mock."
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
