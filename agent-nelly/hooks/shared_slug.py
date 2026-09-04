"""Shared project slug utility for consolidating duplicated logic across plugins.

The project_slug() function is copy-pasted in:
- agent-nelly/hooks/nelly_memory.py
- agent-isdd/hooks/sdd_memory.py
- agent-tdd/hooks/tdd_state.py

This module consolidates the canonical implementation.
"""

import os
import re
from typing import Optional


def get_project_slug(cwd: Optional[str] = None) -> str:
    """Deterministic collision-resistant slug from an absolute project path.

    Args:
        cwd: Working directory (default: current working directory)

    Returns:
        A slug derived from the absolute path by replacing non-alphanumeric
        characters with hyphens, lowercased.

    Examples:
        /Users/jay/Codebase/AI/plugins/claude/agent-nelly → users-jay-codebase-ai-plugins-claude-agent-nelly
        /home/user/project → home-user-project
    """
    if cwd is None:
        cwd = os.getcwd()

    absp = os.path.abspath(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"
