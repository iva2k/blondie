"""TASKS.md parser and manager for Blondie."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


class TaskStatus(Enum):
    """Task status."""
    DONE = "Done"
    TODO = "Todo"


@dataclass
class Task:
    """Task."""
    id: str
    priority: str | None  # P0, P1, P2
    title: str
    depends_on: list[str]
    status: TaskStatus
    raw_line: str
    project_id: str

    @property
    def full_id(self) -> str:
        """Compose full ID (PROJECT-123)."""
        return f"{self.project_id}-{self.id}"

    @property
    def branch_name(self) -> str:
        """Compose branch name for the Task."""
        return f"task-{self.full_id.lower()}"


class TasksManager:
    """Full TASKS.md lifecycle: parse → claim → complete → persist."""

    def __init__(self, tasks_path: Path, project_id: str = "BLONDIE"):
        self.tasks_path = tasks_path
        self.project_id = project_id
        self.tasks: list[Task] = []
        self._parse()

    def _parse(self) -> None:
        """Parse TASKS.md markdown checklists."""
        if not self.tasks_path.exists():
            console.print(f"⚠️  [yellow]{self.tasks_path}[/yellow] not found")
            return

        content = self.tasks_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        current_section = TaskStatus.TODO

        self.tasks.clear()

        for _line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Section headers
            section_match = re.match(
                r"##\s*(Done|Todo)", line_stripped, re.I)
            if section_match:
                current_section = TaskStatus(section_match.group(1).title())
                continue

            # Ignore "In Progress" section header if it exists (migration)
            if re.match(r"##\s*In Progress", line_stripped, re.I):
                current_section = TaskStatus.TODO  # Map to Todo
                continue

            # Task pattern: [ ] 003 | P1 | Git wrapper | 001, 002
            pattern = r"""
                (?:[-*]\s+)?                # Optional bullet
                \[([ x])\]                  # Checkbox
                \s*
                ([A-Z0-9]+)                 # Task ID (003)
                \s*\|\s*
                (P\d+|HIGH|MEDIUM|LOW)?     # Priority
                \s*\|\s*
                (.+?)                       # Title
                (?:\s*\|\s*(.*))?$          # Optional depends_on
            """
            task_match = re.match(pattern, line_stripped, re.VERBOSE)

            if task_match:
                checked, task_id, priority, title, depends_str = task_match.groups()
                status = TaskStatus.DONE if checked.strip() == "x" else current_section

                depends_on = []
                if depends_str and depends_str.strip():
                    depends_on = [d.strip() for d in depends_str.split(",") if d.strip()]

                self.tasks.append(Task(
                    id=task_id.strip(),
                    priority=priority.strip() if priority else None,
                    title=title.strip(),
                    depends_on=depends_on,
                    status=status,
                    raw_line=line,
                    project_id=self.project_id
                ))

    def get_todo_tasks(self) -> list[Task]:
        """Get available tasks, sorted by priority."""
        todos = [t for t in self.tasks if t.status == TaskStatus.TODO]
        # P0 > P1 > P2 > unprioritized
        todos.sort(key=lambda t: t.priority or "ZZ")
        return todos

    def complete_task(self, task_id: str) -> bool:
        """Mark task complete."""
        # Handle both "003" and "BLONDIE-003"
        clean_id = task_id.replace(f"{self.project_id}-", "")
        for task in self.tasks:
            if task.id == clean_id:
                task.status = TaskStatus.DONE
                self._save()
                console.print(
                    f"✅ Completed [bold green]{task.full_id}[/]: {task.title}")
                return True
        return False

    def get_next_task(self) -> Task | None:
        """Get highest priority available task."""
        todos = self.get_todo_tasks()
        return todos[0] if todos else None

    def _save(self) -> None:
        """Write tasks back to TASKS.md with sections."""
        content = ["# Blondie Tasks\n\nStatus: id | priority | title | depends_on\n"]

        for status in [TaskStatus.DONE, TaskStatus.TODO]:
            tasks_in_status = [t for t in self.tasks if t.status == status]
            if tasks_in_status:
                content.append(f"\n## {status.value}\n")
                for task in tasks_in_status:
                    checked = "x" if status == TaskStatus.DONE else " "
                    priority = task.priority or ""
                    depends = ", ".join(task.depends_on)
                    content.append(
                        f"- [{checked}] {task.id} | {priority} | {task.title} | {depends}\n")

        self.tasks_path.write_text("".join(content), encoding="utf-8")

    def print_summary(self) -> None:
        """Rich table summary."""
        table = Table(title="Blondie Task Status")
        table.add_column("ID", style="cyan")
        table.add_column("Priority", style="magenta")
        table.add_column("Title", style="white")
        table.add_column("Status", style="green")
        table.add_column("Depends On", style="blue")

        for task in self.tasks:
            table.add_row(
                task.full_id,
                task.priority or "",
                task.title[:50],
                task.status.value,
                ", ".join(task.depends_on)
            )

        console.print(table)


def main():
    """Simple unit test: Try to read project.yaml for ID."""
    # pylint: disable-next=import-outside-toplevel
    from agent.project import Project

    project_id = "BLONDIE"
    try:
        project = Project.from_file(Path(".agent/project.yaml"))
        project_id = project.id.upper()
    except Exception:
        pass

    manager = TasksManager(Path(".agent/TASKS.md"), project_id=project_id)
    manager.print_summary()

    next_task = manager.get_next_task()
    if next_task:
        print(f"\nNext task: {next_task.full_id} - {next_task.title}")

if __name__ == "__main__":
    main()
