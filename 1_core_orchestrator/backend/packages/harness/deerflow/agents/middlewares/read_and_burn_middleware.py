"""Middleware to clean up Base64 images from message history after the model has viewed them."""

import logging

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.config.app_config import get_app_config

logger = logging.getLogger(__name__)


class ReadAndBurnMiddleware(AgentMiddleware[AgentState]):
    """Middleware to clean up Base64 images from message history to save context tokens.
    
    This runs after the model completes a turn. If the model did NOT output tool calls
    (meaning it gave a final answer to the user), this middleware scans the history
    for any HumanMessages containing Base64 image_urls and replaces them with a 
    text placeholder.
    """

    state_schema = AgentState

    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        """Clean up Base64 images if the model has finished its reasoning."""
        vision_cfg = getattr(get_app_config(), "vision", None) or {}
        if not vision_cfg.get("enabled", False) or not vision_cfg.get("read_and_burn", {}).get("enabled", False):
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        # Check the last message (which should be the AIMessage just generated)
        last_msg = messages[-1]
        
        # If the LLM is calling tools, do NOT burn the image yet. It might still need it in the next turn.
        if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
            return None

        placeholder_text = vision_cfg.get("read_and_burn", {}).get(
            "placeholder", "[已分析的临床照片 — 图片数据已清理，以节省 Tokens]"
        )

        modified_messages = []

        # Find any HumanMessage that contains image_url blocks
        for msg in messages:
            if not isinstance(msg, HumanMessage):
                continue
                
            if not isinstance(msg.content, list):
                continue
                
            has_image = False
            new_content = []
            
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == "image_url":
                    has_image = True
                    # Replace with placeholder
                    new_content.append({"type": "text", "text": placeholder_text})
                else:
                    new_content.append(block)
                    
            if has_image:
                logger.info(f"Burning Base64 image data from HumanMessage {msg.id}")
                new_msg = HumanMessage(
                    content=new_content,
                    additional_kwargs=msg.additional_kwargs,
                    id=msg.id,
                    name=msg.name
                )
                modified_messages.append(new_msg)

        if not modified_messages:
            return None

        # By returning these messages with the exact same IDs, 
        # the LangGraph `add_messages` reducer will update the existing messages in state.
        return {"messages": modified_messages}
