# src/agent/__init__.py

"""Blondie core agent package."""

from .context import ContextGatherer
from .executor import CommandResult, Executor
from .llm_config import LLMConfig
from .loop import BlondieAgent
from .policy import AutonomyRule, Policy
from .progress import ProgressManager
from .project import Project
from .router import LLMRouter
from .tasks import TasksManager
from .tooled import TOOL_DEFINITIONS, ToolHandler

__version__ = "0.1.0"
__all__ = [
    "ContextGatherer",
    "Executor",
    "CommandResult",
    "BlondieAgent",
    "LLMConfig",
    "LLMRouter",
    "Policy",
    "AutonomyRule",
    "ProgressManager",
    "Project",
    "TasksManager",
    "TOOL_DEFINITIONS",
    "ToolHandler",
]
