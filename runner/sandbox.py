"""Run agent commands inside the attempt workspace with time, CPU and output limits."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import settings

_OUTPUT_CHARS = 4000
_MAX_FILE_KB = 50 * 1024  # largest file a command may write


@dataclass
class SandboxResult:
    exit_code: int | None  # None when the command timed out
    stdout: str
    stderr: str

    @property
    def timed_out(self) -> bool:
        return self.exit_code is None

    def to_text(self) -> str:
        """Compact form fed back to the model."""
        if self.timed_out:
            return f"Command timed out after {settings.execution_timeout_seconds} seconds."
        out = f"Exit code: {self.exit_code}\n"
        if self.stdout:
            out += f"STDOUT:\n{self.stdout[-_OUTPUT_CHARS:]}\n"
        if self.stderr:
            out += f"STDERR:\n{self.stderr[-_OUTPUT_CHARS:]}\n"
        return out


def run(command: str, workspace: Path) -> SandboxResult:
    """Run `command` in a shell rooted at the workspace.

    The process gets a minimal environment (no server secrets), CPU and file-size
    limits, and its whole process group is killed on timeout.
    """
    # ponytail: process-level limits only, no network or filesystem isolation; use a
    # container (gVisor / Cloud Run job) per attempt before running untrusted repos.
    timeout = settings.execution_timeout_seconds
    limited = f"ulimit -t {timeout}; ulimit -f {_MAX_FILE_KB}; {command}"
    # Throwaway HOME so tool caches (pip, npm) never land in the repo diff.
    with tempfile.TemporaryDirectory(prefix="tryout-home-") as home:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": home,
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        proc = subprocess.Popen(
            limited,
            shell=True,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,  # own process group, so a timeout kills child processes too
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            return SandboxResult(exit_code=None, stdout=stdout, stderr=stderr)
    return SandboxResult(exit_code=proc.returncode, stdout=stdout, stderr=stderr)
