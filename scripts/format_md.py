#!/usr/bin/env python3
# scripts/format_md.py

"""Format markdown files to use asterisks for bullet lists."""

import re
from pathlib import Path


def format_file(path: Path) -> None:
    """
    Format markdown file:

      * use asterisks for bullet lists
    """
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    lines = original.splitlines()
    new_lines = []
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            new_lines.append(line)
            continue
        elif i == 0 and stripped == "---":
            in_frontmatter = True

        if stripped.startswith("```"):
            in_code_block = not in_code_block

        if not in_code_block:
            # Replace "- " with "* " at the start of the line or after whitespace
            # Avoid changing "---" (hr)
            if re.match(r"^\s*-\s", line) and not stripped.startswith("---"):
                line = re.sub(r"^(\s*)-\s", r"\1* ", line, count=1)

        new_lines.append(line)

    # Restore trailing newline
    new_content = "\n".join(new_lines) + "\n"
    if new_content != original:
        path.write_text(new_content, encoding="utf-8")
        print(f"Formatted {path}")


if __name__ == "__main__":
    # Walk directory, excluding common ignores
    root = Path(".")
    for p in root.rglob("*.md"):
        parts = p.parts
        if any(x in parts for x in ["_tmp", ".git", "node_modules", ".venv", "__pycache__"]):
            continue
        format_file(p)
