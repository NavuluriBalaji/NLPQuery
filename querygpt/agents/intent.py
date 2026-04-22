"""
Intent Agent

Classifies the user's natural language question into one or more workspaces
AND enhances (expands) the question with richer context for downstream RAG.

Two jobs, but both are tightly cohesive: understand the question better.
"""
from __future__ import annotations

import json
import logging

from querygpt.agents.base import Agent
from querygpt.llm.base import LLMProvider
from querygpt.models import AgentStatus, IntentAgentInput, IntentAgentOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert data analyst assistant. Your job is to:
1. Understand a user's natural language question about data.
2. Map it to one or more relevant business domains / workspaces from the
   provided list.
3. Rewrite the question as a richer, context-full version that will help
   an AI find relevant database tables and SQL patterns.

Rules:
- Only choose workspaces from the provided list. If none fit, return [].
- The enhanced question should preserve the original intent but add explicit
  data concepts, likely table names, columns, filters, and aggregations.
- Respond ONLY with valid JSON and nothing else.

Response format:
{
  "matched_workspaces": ["workspace1", "workspace2"],
  "enhanced_question": "...",
  "reasoning": "..."
}
"""


class IntentAgent(Agent[IntentAgentInput, IntentAgentOutput]):
    """
    SRP : only classifies intent and enhances the prompt.
    DIP : depends on LLMProvider abstraction, not a concrete LLM class.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def run(self, input_: IntentAgentInput) -> IntentAgentOutput:
        workspaces_str = "\n".join(f"- {w}" for w in input_.available_workspaces)

        user_msg = f"""\
Available workspaces:
{workspaces_str}

User question:
{input_.user_question}

Return JSON as specified.
"""
        try:
            raw = self._llm.system_user(_SYSTEM_PROMPT, user_msg, response_format="json")
            data = json.loads(raw)
            return IntentAgentOutput(
                status=AgentStatus.SUCCESS,
                matched_workspaces=data.get("matched_workspaces", []),
                enhanced_question=data.get("enhanced_question", input_.user_question),
                reasoning=data.get("reasoning"),
            )
        except Exception as exc:
            logger.warning("IntentAgent failed: %s. Falling back to original question.", exc)
            return IntentAgentOutput(
                status=AgentStatus.ERROR,
                matched_workspaces=[],
                enhanced_question=input_.user_question,
                reasoning=str(exc),
            )