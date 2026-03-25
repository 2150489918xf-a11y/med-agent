"""Built-in subagent configurations."""

from .imaging_agent import IMAGING_AGENT_CONFIG
from .medical_knowledge_agent import MEDICAL_KNOWLEDGE_AGENT_CONFIG

__all__ = [
    "IMAGING_AGENT_CONFIG",
    "MEDICAL_KNOWLEDGE_AGENT_CONFIG",
]

# Registry of built-in subagents
BUILTIN_SUBAGENTS = {
    "imaging-agent": IMAGING_AGENT_CONFIG,
    "medical-knowledge-agent": MEDICAL_KNOWLEDGE_AGENT_CONFIG,
}
