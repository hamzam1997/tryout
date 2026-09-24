"""Architectural context string generation, directory tree rendering, and token budgeting."""

from schemas import FileCategory, ScannedFile


CATEGORY_PRIORITY = [
    FileCategory.MANIFEST,
    FileCategory.CONFIG,
    FileCategory.ENTRYPOINT,
    FileCategory.MODEL,
    FileCategory.ROUTE,
    FileCategory.INTEGRATION,
    FileCategory.DOC,
    FileCategory.OTHER,
]

CATEGORY_TITLES = {
    FileCategory.MANIFEST: "Manifests & Dependencies",
    FileCategory.CONFIG: "Configuration & CODEOWNERS",
    FileCategory.ENTRYPOINT: "Application Entrypoints",
    FileCategory.MODEL: "Data Models & Schemas",
    FileCategory.ROUTE: "API Routes & Controllers",
    FileCategory.INTEGRATION: "External Integrations & Clients",
    FileCategory.DOC: "Architecture & Documentation",
    FileCategory.OTHER: "Supporting Application Logic",
}


def build_directory_tree(paths: list[str]) -> str:
    """
    Build a compact visual text tree from a list of relative POSIX paths.
    """
    if not paths:
        return ""

    # Build nested dictionary tree
    tree: dict = {}
    for p in sorted(paths):
        parts = p.split("/")
        curr = tree
        for part in parts:
            curr = curr.setdefault(part, {})

    lines: list[str] = []

    def _render(node: dict, prefix: str = ""):
        items = sorted(node.keys())
        for idx, key in enumerate(items):
            is_last = idx == len(items) - 1
            branch = "└── " if is_last else "├── "
            lines.append(f"{prefix}{branch}{key}")
            child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
            _render(node[key], child_prefix)

    _render(tree)
    return "\n".join(lines)


def truncate_file_content(content: str, max_chars: int) -> tuple[str, bool]:
    """
    Truncate file content if it exceeds max_chars, appending a truncation notice.
    Returns (content, is_truncated).
    """
    if len(content) <= max_chars:
        return content, False

    half = max_chars // 2
    truncated_msg = f"\n\n... [TRUNCATED: Showing {max_chars} of {len(content)} characters] ...\n\n"
    # Keep beginning and end for code readability
    truncated_content = content[:half] + truncated_msg + content[-half:]
    return truncated_content, True


def generate_context_string(
    repo_name: str,
    files: list[ScannedFile],
    max_total_chars: int = 120_000,
    max_file_chars: int = 15_000,
) -> str:
    """
    Generate a compact, token-efficient architectural context string for LLM consumption.
    Enforces per-file and overall character budgets according to category priority.
    """
    tree_text = build_directory_tree([f.path for f in files])

    sections: list[str] = [
        f"# Repository Architectural Skeleton: {repo_name}",
        "",
        "## Directory Structure",
        "```",
        tree_text,
        "```",
        "",
    ]

    current_len = sum(len(s) + 1 for s in sections)

    # Sort files by category priority, then by path
    sorted_files = sorted(
        files,
        key=lambda f: (
            CATEGORY_PRIORITY.index(f.category)
            if f.category in CATEGORY_PRIORITY
            else 99,
            f.path,
        ),
    )

    # Group by category
    by_category: dict[FileCategory, list[ScannedFile]] = {}
    for f in sorted_files:
        by_category.setdefault(f.category, []).append(f)

    for cat in CATEGORY_PRIORITY:
        cat_files = by_category.get(cat, [])
        if not cat_files:
            continue

        cat_title = CATEGORY_TITLES.get(cat, cat.value)
        file_blocks: list[str] = []
        for file_entry in cat_files:
            if not file_entry.content.strip():
                continue

            remaining_budget = max_total_chars - current_len
            if remaining_budget <= 200:
                file_blocks.append(
                    f"\n> [!NOTE]\n> Budget reached ({max_total_chars} chars). Omitted remaining files."
                )
                break

            # Bound per-file length
            effective_max_chars = min(max_file_chars, remaining_budget - 100)
            content, is_trunc = truncate_file_content(file_entry.content, effective_max_chars)
            file_entry.truncated = is_trunc

            # Detect language for fenced code block
            ext = file_entry.path.split(".")[-1].lower() if "." in file_entry.path else ""
            lang_map = {
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "go": "go",
                "rs": "rust",
                "json": "json",
                "yaml": "yaml",
                "yml": "yaml",
                "toml": "toml",
                "md": "markdown",
                "txt": "text",
            }
            code_lang = lang_map.get(ext, "")

            file_block = [
                f"### `{file_entry.path}` ({file_entry.category.value})",
                f"```{code_lang}",
                content,
                "```",
                "",
            ]
            block_str = "\n".join(file_block)
            current_len += len(block_str)
            file_blocks.append(block_str)

        if file_blocks:
            sections.append(f"## {cat_title}")
            sections.append("")
            sections.extend(file_blocks)

        if current_len >= max_total_chars:
            break

    return "\n".join(sections)
