# src/lib/gitignore.py

"""Gitignore matcher."""

from __future__ import annotations

import fnmatch
from pathlib import Path


class GitIgnore:
    """Handles .gitignore logic."""

    def __init__(self, root: Path):
        self.root = root
        self.patterns: list[tuple[str, bool]] = []
        self._load()

    def _load(self) -> None:
        """Load patterns from .gitignore."""
        # Always ignore .git
        self.patterns.append((".git", False))

        gitignore_path = self.root / ".gitignore"
        if not gitignore_path.exists():
            return

        content = gitignore_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            is_negative = line.startswith("!")
            if is_negative:
                line = line[1:]

            # Normalize
            line = line.replace("\\", "/")
            self.patterns.append((line, is_negative))

    def is_ignored(self, path: Path) -> bool:
        """Check if path is ignored."""
        try:
            rel_path = path.relative_to(self.root)
        except ValueError:
            return False

        path_str = str(rel_path).replace("\\", "/")
        parts = rel_path.parts

        ignored = False

        for pattern, is_negative in self.patterns:
            match = False

            # Directory match (ends with /)
            if pattern.endswith("/"):
                prefix = pattern.rstrip("/")
                # Check if path starts with this dir
                if path_str == prefix or path_str.startswith(prefix + "/"):
                    match = True
                # Check if any parent component matches (e.g. build/ matches src/build/out)
                # We check parts[:-1] because the pattern is a directory, so it shouldn't match the file itself if it has that name
                elif prefix in parts[:-1]:
                    match = True

            # Pattern with slash (path match)
            elif "/" in pattern:
                if fnmatch.fnmatch(path_str, pattern.lstrip("/")):
                    match = True

            # Pattern without slash (name match)
            else:
                if any(fnmatch.fnmatch(p, pattern) for p in parts):
                    match = True

            if match:
                ignored = not is_negative

        return ignored
