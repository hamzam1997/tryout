"""Safe filesystem and execution tools for the agent harness."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _enforce_bounds(root: Path, target: str | Path) -> Path:
    resolved = (root / target).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Path {target} escapes the workspace root.")
    return resolved


def search_code(workspace: Path, query: str) -> str:
    """Use grep to search code inside the workspace."""
    try:
        result = subprocess.run(
            ["grep", "-rnI", query, "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = result.stdout.strip()
        if not out:
            return "No matches found."
        # Truncate if too large
        if len(out) > 8000:
            return out[:8000] + "\n...[truncated]"
        return out
    except subprocess.TimeoutExpired:
        return "Search timed out."
    except Exception as e:
        return f"Error during search: {e}"


def list_directory(workspace: Path, path: str = ".") -> str:
    """List contents of a directory."""
    target_dir = _enforce_bounds(workspace, path)
    if not target_dir.is_dir():
        return f"Directory not found: {path}"
    
    items = []
    for item in target_dir.iterdir():
        if item.name.startswith(".") and item.name not in (".env.example", ".gitignore"):
            continue
        if item.name == "__pycache__":
            continue
        suffix = "/" if item.is_dir() else ""
        items.append(f"{item.name}{suffix}")
    
    return "\n".join(sorted(items))


def view_file(workspace: Path, path: str, start_line: int = 1, end_line: int = 500) -> str:
    """View specific lines of a file."""
    target = _enforce_bounds(workspace, path)
    if not target.is_file():
        return f"File not found: {path}"
    
    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return "Cannot read binary file."
    
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    
    if start_idx >= len(lines):
        return f"File has only {len(lines)} lines."
    
    output = []
    for i in range(start_idx, end_idx):
        output.append(f"{i + 1}: {lines[i]}")
    
    return "".join(output)


def edit_file(workspace: Path, path: str, target_chunk: str, replacement_chunk: str) -> str:
    """Replace an exact chunk of text in a file."""
    target = _enforce_bounds(workspace, path)
    if not target.is_file():
        return f"File not found: {path}"
    
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "Cannot edit binary file."
    
    if target_chunk not in content:
        return "Error: target_chunk not found in file exactly as provided. Please verify spacing and try again."
    
    occurrences = content.count(target_chunk)
    if occurrences > 1:
        return f"Error: target_chunk is ambiguous (found {occurrences} times). Provide more lines of context."
    
    new_content = content.replace(target_chunk, replacement_chunk)
    target.write_text(new_content, encoding="utf-8")
    return f"Successfully updated {path}."


def create_file(workspace: Path, path: str, content: str) -> str:
    """Create a new file with content."""
    target = _enforce_bounds(workspace, path)
    if target.exists():
        return f"Error: File {path} already exists. Use edit_file instead."
    
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Successfully created {path}."


def run_tests(workspace: Path, command: str) -> str:
    """Run tests or arbitrary sandboxed commands."""
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = f"Exit code: {result.returncode}\n"
        if result.stdout:
            out += f"STDOUT:\n{result.stdout[:4000]}\n"
        if result.stderr:
            out += f"STDERR:\n{result.stderr[:4000]}\n"
        return out
    except subprocess.TimeoutExpired:
        return "Command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {e}"
