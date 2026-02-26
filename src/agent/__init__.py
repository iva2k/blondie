# src/agent/__init__.py

"""Blondie core agent package."""

from .executor import CommandResult, Executor
from .loop import BlondieAgent
from .policy import AutonomyRule, Policy
from .progress import ProgressManager
from .project import Project
from .tasks import TasksManager

__version__ = "0.1.0"
__all__ = [
    "Executor",
    "CommandResult",
    "BlondieAgent",
    "Policy",
    "AutonomyRule",
    "ProgressManager",
    "Project",
    "TasksManager",
]
