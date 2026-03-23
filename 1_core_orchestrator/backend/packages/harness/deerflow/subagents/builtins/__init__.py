"""Built-in subagent configurations."""

from .bash_agent import BASH_AGENT_CONFIG
from .general_purpose import GENERAL_PURPOSE_CONFIG
from .a2_exam import A2_EXAM_CONFIG
from .a3_diagnosis import A3_DIAGNOSIS_CONFIG

__all__ = [
    "GENERAL_PURPOSE_CONFIG",
    "BASH_AGENT_CONFIG",
    "A2_EXAM_CONFIG",
    "A3_DIAGNOSIS_CONFIG",
]

# Registry of built-in subagents
BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
    "a2_exam": A2_EXAM_CONFIG,
    "a3_diagnosis": A3_DIAGNOSIS_CONFIG,
}
