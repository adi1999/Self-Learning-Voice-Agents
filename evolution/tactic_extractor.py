"""LLM-based extraction of winning tactics from high-scoring conversations."""

import logging
from uuid import uuid4

from config.settings import ANALYSIS_MODEL, TACTIC_SCORE_THRESHOLD
from core.llm_client import llm_call_json
from core.models import Conversation, FailedApproach, StrategyTactic, TurnReference
from core.playbook import get_tactics_for_persona, save_failed_approach, save_tactic

logger = logging.getLogger(__name__)

TACTIC_EXTRACTION_PROMPT = """You are analyzing a high-scoring debt collection conversation to extract reusable tactics.

CONVERSATION (persona: {persona_type}, score: {score:.2f}):
{transcript}

TASK:
Extract 1-3 specific tactics that made this conversation successful. Each tactic should be:
- Concrete and actionable (not vague like "be empathetic")
- Tied to a specific prompt section (identity, objective, opening, strategy, closing)
- Something that could be reused in future conversations with similar personas

EXISTING TACTICS FOR THIS PERSONA (avoid duplicates):
{existing_tactics}

Respond with ONLY a JSON array:
[
  {{
    "tactic": "<1-3 sentence description of what worked>",
    "prompt_section": "<identity|objective|opening|strategy|closing>",
    "example_turn_indices": [<int>, <int>]
  }}
]

If all tactics are already covered by existing ones, return an empty array: []"""


def _format_transcript(conv: Conversation) -> str:
    lines = []
    for turn in conv.turns:
        role = "AGENT" if turn.role == "agent" else "BORROWER"
        lines.append(f"  [Turn {turn.index}] {role}: {turn.content}")
    return "\n".join(lines)


def _format_existing_tactics(tactics: list[StrategyTactic]) -> str:
    if not tactics:
        return "  (none yet)"
    return "\n".join(f"  - {t.tactic}" for t in tactics)


async def extract_tactics_from_conversations(
    conversations: list[Conversation],
    version_id: str,
    run_id: str | None = None,
) -> list[StrategyTactic]:
    """Extract winning tactics from high-scoring conversations.

    Only processes conversations scoring >= TACTIC_SCORE_THRESHOLD.
    Returns list of newly saved tactics.
    """
    high_scoring = [
        c for c in conversations
        if c.eval_result and c.eval_result.weighted_total >= TACTIC_SCORE_THRESHOLD
    ]

    if not high_scoring:
        logger.info("No conversations above tactic threshold — skipping extraction")
        return []

    logger.info(f"Extracting tactics from {len(high_scoring)} high-scoring conversations")
    new_tactics: list[StrategyTactic] = []

    for conv in high_scoring:
        persona = conv.persona_type or "unknown"
        existing = get_tactics_for_persona(persona, limit=10)

        prompt = TACTIC_EXTRACTION_PROMPT.format(
            persona_type=persona,
            score=conv.eval_result.weighted_total,
            transcript=_format_transcript(conv),
            existing_tactics=_format_existing_tactics(existing),
        )

        try:
            result = await llm_call_json(
                system="You are an expert at analyzing conversational AI tactics. Respond only in JSON.",
                messages=[{"role": "user", "content": prompt}],
                model=ANALYSIS_MODEL,
                max_tokens=2048,
            )
        except Exception:
            logger.warning(f"Tactic extraction failed for {conv.id}", exc_info=True)
            continue

        if not isinstance(result, list):
            continue

        for item in result:
            example_indices = item.get("example_turn_indices", [])
            example_turns = [
                TurnReference(
                    conversation_id=conv.id,
                    turn_index=idx,
                    content=conv.turns[idx].content if idx < len(conv.turns) else "",
                )
                for idx in example_indices
            ]

            tactic = StrategyTactic(
                id=f"tactic_{uuid4().hex[:8]}",
                persona_type=persona,
                prompt_section=item.get("prompt_section", "strategy").lower(),
                tactic=item["tactic"],
                example_turns=example_turns,
                score_impact=conv.eval_result.weighted_total,
                source_version_id=version_id,
                source_run_id=run_id,
            )
            save_tactic(tactic)
            new_tactics.append(tactic)
            logger.info(f"Saved tactic: [{tactic.prompt_section}] {tactic.tactic[:60]}...")

    logger.info(f"Extracted {len(new_tactics)} new tactics total")
    return new_tactics


def record_failed_candidates(
    parent: "AgentVersion",
    candidates: list["AgentVersion"],
    winner: "AgentVersion | None",
    run_id: str | None = None,
) -> list[FailedApproach]:
    """Record candidates that were not promoted as failed approaches."""
    from config.settings import PERSONA_ARCHETYPES

    if not parent.scores:
        return []

    failures: list[FailedApproach] = []
    for candidate in candidates:
        if winner and candidate.id == winner.id:
            continue
        if not candidate.scores:
            continue

        # Determine failure reason
        if candidate.scores.aggregate <= parent.scores.aggregate:
            reason = "no_improvement"
        else:
            reason = "regression"

        # Calculate per-persona regressions
        regressions: dict[str, float] = {}
        for persona in PERSONA_ARCHETYPES:
            if persona in parent.scores.per_persona and persona in candidate.scores.per_persona:
                delta = (
                    candidate.scores.per_persona[persona].weighted_total
                    - parent.scores.per_persona[persona].weighted_total
                )
                if delta < 0:
                    regressions[persona] = round(delta, 3)

        failure = FailedApproach(
            id=f"fail_{uuid4().hex[:8]}",
            target_section=candidate.mutation_target or "unknown",
            description=candidate.rationale or "No rationale recorded",
            failure_reason=reason,
            parent_version_id=parent.id,
            candidate_version_id=candidate.id,
            score_before=parent.scores.aggregate,
            score_after=candidate.scores.aggregate,
            persona_regressions=regressions,
            source_run_id=run_id,
        )
        save_failed_approach(failure)
        failures.append(failure)
        logger.info(f"Recorded failure: [{failure.target_section}] {reason} ({failure.score_before:.2f} → {failure.score_after:.2f})")

    return failures
