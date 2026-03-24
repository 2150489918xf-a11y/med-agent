"""Built-in subagent configurations."""

from .bash_agent import BASH_AGENT_CONFIG
from .general_purpose import GENERAL_PURPOSE_CONFIG
from .imaging import IMAGING_CONFIG
from .research import RESEARCH_CONFIG

__all__ = [
    "GENERAL_PURPOSE_CONFIG",
    "BASH_AGENT_CONFIG",
    "IMAGING_CONFIG",
    "RESEARCH_CONFIG",
]

# Registry of built-in subagents
BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
    "imaging": IMAGING_CONFIG,
    "research": RESEARCH_CONFIG,
}
