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
    IN_PROGRESS = "In Progress"
    TODO = "Todo"


@dataclass
class Task:
    """Task."""
    id: str
    priority: str | None  # P0, P1, P2
    title: str
    branch: str | None
    status: TaskStatus
    raw_line: str

    @property
    def branch_name(self) -> str:
        """Compose branch name for the Task."""
        return f"{self.id.lower().replace(' ', '-')}"


class TasksManager:
    """Full TASKS.md lifecycle: parse → claim → complete → persist."""

    def __init__(self, tasks_path: Path):
        self.tasks_path = tasks_path
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
                r"##\s*(Done|In Progress|Todo)", line_stripped, re.I)
            if section_match:
                current_section = TaskStatus(section_match.group(1).title())
                continue

            # Task pattern: [ ] P1 | BLONDIE-003 | Git wrapper | task-BLONDIE-003
            pattern = r"""
                (?:[-*]\s+)?                # Optional bullet
                \[([ x])\]                  # Checkbox
                \s*
                (P\d+|HIGH|MEDIUM|LOW)?     # Priority
                \s*\|\s*
                ([A-Z0-9-]+)                # Task ID
                \s*\|\s*
                (.+?)                       # Title
                (?:\s*\|\s*(.*))?$          # Optional branch
            """
            task_match = re.match(pattern, line_stripped, re.VERBOSE)

            if task_match and current_section:
                checked, priority, task_id, title, branch = task_match.groups()
                status = TaskStatus.DONE if checked.strip() == "x" else current_section

                self.tasks.append(Task(
                    id=task_id.strip(),
                    priority=priority.strip() if priority else None,
                    title=title.strip(),
                    branch=branch.strip() if branch else None,
                    status=status,
                    raw_line=line
                ))

    def get_todo_tasks(self) -> list[Task]:
        """Get available tasks, sorted by priority."""
        todos = [t for t in self.tasks if t.status == TaskStatus.TODO]
        # P0 > P1 > P2 > unprioritized
        todos.sort(key=lambda t: t.priority or "ZZ")
        return todos

    def claim_task(self, task_id: str) -> Task | None:
        """Atomically claim task by moving to In Progress."""
        for task in self.tasks:
            if task.id == task_id and task.status == TaskStatus.TODO:
                task.status = TaskStatus.IN_PROGRESS
                task.branch = task.branch_name
                self._save()
                console.print(
                    f"✅ Claimed [bold cyan]{task_id}[/]: {task.title}")
                return task
        return None

    def complete_task(self, task_id: str) -> bool:
        """Mark task complete."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = TaskStatus.DONE
                self._save()
                console.print(
                    f"✅ Completed [bold green]{task_id}[/]: {task.title}")
                return True
        return False

    def get_next_task(self) -> Task | None:
        """Get highest priority available task."""
        todos = self.get_todo_tasks()
        return todos[0] if todos else None

    def _save(self) -> None:
        """Write tasks back to TASKS.md with sections."""
        content = ["# Blondie Tasks\n"]

        for status in [TaskStatus.DONE, TaskStatus.IN_PROGRESS, TaskStatus.TODO]:
            tasks_in_status = [t for t in self.tasks if t.status == status]
            if tasks_in_status:
                content.append(f"\n## {status.value}\n")
                for task in tasks_in_status:
                    checked = "x" if status == TaskStatus.DONE else " "
                    priority = task.priority or ""
                    branch = task.branch or ""
                    content.append(
                        f"- [{checked}] {priority} | {task.id} | {task.title} | {branch}\n")

        self.tasks_path.write_text("".join(content), encoding="utf-8")

    def print_summary(self) -> None:
        """Rich table summary."""
        table = Table(title="Blondie Task Status")
        table.add_column("ID", style="cyan")
        table.add_column("Priority", style="magenta")
        table.add_column("Title", style="white")
        table.add_column("Status", style="green")
        table.add_column("Branch", style="blue")

        for task in self.tasks:
            table.add_row(
                task.id,
                task.priority or "",
                task.title[:50],
                task.status.value,
                task.branch or ""
            )

        console.print(table)


if __name__ == "__main__":
    manager = TasksManager(Path(".agent/TASKS.md"))
    manager.print_summary()

    next_task = manager.get_next_task()
    if next_task:
        print(f"\nNext task: {next_task.id} - {next_task.title}")
        manager.claim_task(next_task.id)
