# src/agent/progress.py

"""Progress manager for tracking agent actions."""

import datetime
from pathlib import Path


class ProgressManager:
    """Manages the progress.txt file."""

    def __init__(self, path: Path):
        self.path = path

    def add_action(self, action: str, details: str, status: str = "DONE") -> None:
        """Append an action to the progress file."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {action}: {details} ({status})\n"

        # Ensure parent exists
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry)

    def read(self) -> str:
        """Read current progress history."""
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    def clear(self) -> None:
        """Clear progress history."""
        if self.path.exists():
            self.path.write_text("", encoding="utf-8")
