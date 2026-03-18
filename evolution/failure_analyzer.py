"""Analyze scored conversations to identify top failure patterns."""

import logging

from config.settings import ANALYSIS_MODEL
from core.llm_client import llm_call_json
from core.models import Conversation, FailurePattern, TurnReference

logger = logging.getLogger(__name__)

FAILURE_ANALYSIS_PROMPT = """You are analyzing conversation logs from a debt collection voice agent to identify failure patterns.

Here are {n} scored conversations:

{conversations}

TASK:
1. Identify the top 3 recurring failure patterns across these conversations
2. For each pattern:
   a. Describe it in one sentence
   b. Cite 2-3 specific turn examples (conversation ID + turn number + text)
   c. Map it to the responsible prompt section:
      IDENTITY | OBJECTIVE | OPENING | STRATEGY | CLOSING
      (COMPLIANCE is immutable — never target it)
   d. Suggest the direction of the fix (what the section should do differently,
      NOT the specific wording)

IMPORTANT:
- Focus on patterns that appear across multiple conversations, not one-off issues
- Prioritize failures that directly impact goal completion
- The "direction" should be actionable but NOT prescriptive — let the rewriter decide the exact wording

Respond with ONLY a JSON array of 3 objects:
[
  {{
    "description": "<one-sentence description>",
    "target_section": "<identity|objective|opening|strategy|closing>",
    "example_turns": [
      {{"conversation_id": "<id>", "turn_index": <int>, "content": "<text>"}}
    ],
    "suggested_direction": "<direction of fix>"
  }}
]"""


def _format_conversations(conversations: list[Conversation]) -> str:
    """Format conversations with scores and annotations for the analyzer."""
    parts = []
    for conv in conversations:
        lines = [f"--- Conversation {conv.id} (persona: {conv.persona_type}, outcome: {conv.outcome}) ---"]
        if conv.eval_result:
            e = conv.eval_result
            lines.append(
                f"Scores: goal={e.goal_completion:.1f}, quality={e.conversational_quality:.1f}, "
                f"compliance={e.compliance:.1f}, weighted={e.weighted_total:.2f}"
            )
        for turn in conv.turns:
            role = "AGENT" if turn.role == "agent" else "BORROWER"
            if turn.annotations:
                ann_strs = [f"[{a.issue_type}] {a.description}" for a in turn.annotations]
                ann_str = f" {ann_strs}"
            else:
                ann_str = ""
            lines.append(f"  [Turn {turn.index}] {role}: {turn.content}{ann_str}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


async def analyze_failures(conversations: list[Conversation]) -> list[FailurePattern]:
    """Analyze scored conversations and return top 3 failure patterns."""
    formatted = _format_conversations(conversations)
    prompt = FAILURE_ANALYSIS_PROMPT.format(n=len(conversations), conversations=formatted)

    result = await llm_call_json(
        system="You are an expert analyst of conversational AI performance. Respond only in JSON.",
        messages=[{"role": "user", "content": prompt}],
        model=ANALYSIS_MODEL,
        max_tokens=4096,
    )

    patterns = []
    for item in result:
        examples = [
            TurnReference(
                conversation_id=ex["conversation_id"],
                turn_index=ex["turn_index"],
                content=ex["content"],
            )
            for ex in item.get("example_turns", [])
        ]
        patterns.append(
            FailurePattern(
                description=item["description"],
                target_section=item["target_section"].lower(),
                example_turns=examples,
                suggested_direction=item["suggested_direction"],
            )
        )

    logger.info(f"Identified {len(patterns)} failure patterns:")
    for i, p in enumerate(patterns):
        logger.info(f"  {i+1}. [{p.target_section}] {p.description}")

    return patterns
