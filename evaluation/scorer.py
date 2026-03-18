"""Aggregate scores: per-conversation -> per-persona (median) -> aggregate (mean)."""

import asyncio
import logging
from statistics import median, mean

from config.settings import PERSONA_ARCHETYPES, SCORING_WEIGHTS
from core.models import (
    Conversation,
    EvalResult,
    MetricScores,
    PersonaScores,
)
from evaluation.annotator import merge_annotations
from core.llm_client import token_counter
from evaluation.judges import (
    judge_compliance,
    judge_conversational_quality,
    judge_goal_completion,
    judge_response_consistency,
    judge_sentiment_shift,
)

logger = logging.getLogger(__name__)


def compute_weighted_total(
    goal: float,
    quality: float,
    compliance: float,
    consistency: float,
    sentiment: float,
) -> float:
    """Compute per-conversation weighted score, normalized to 0-5."""
    normalized = {
        "goal_completion": goal / 3.0,
        "conversational_quality": (quality - 1) / 4.0,
        "compliance": compliance,
        "response_consistency": consistency,
        "sentiment_shift": (sentiment + 1) / 2.0,
    }
    total = sum(normalized[k] * SCORING_WEIGHTS[k] for k in SCORING_WEIGHTS)
    return round(total * 5.0, 2)


async def evaluate_conversation(conversation: Conversation) -> EvalResult:
    """Run all 5 judges on a conversation and return the eval result."""
    with token_counter() as tc:
        (
            goal,
            (quality, quality_ann, hallucinations, tone),
            (compliance, compliance_ann),
            (consistency, consistency_issues),
            sentiment,
        ) = await asyncio.gather(
            judge_goal_completion(conversation),
            judge_conversational_quality(conversation),
            judge_compliance(conversation),
            judge_response_consistency(conversation),
            judge_sentiment_shift(conversation),
        )

    # Add evaluation tokens to conversation metadata
    if conversation.metadata:
        prev = conversation.metadata.total_tokens or 0
        conversation.metadata.total_tokens = prev + tc.total_tokens

    all_annotations = merge_annotations(conversation, quality_ann, compliance_ann)
    weighted = compute_weighted_total(goal, quality, compliance, consistency, sentiment)

    result = EvalResult(
        goal_completion=goal,
        conversational_quality=quality,
        compliance=compliance,
        response_consistency=consistency,
        sentiment_shift=sentiment,
        weighted_total=weighted,
        turn_annotations=all_annotations,
        hallucinations_found=hallucinations,
        tone_assessment=tone,
        consistency_issues=consistency_issues,
    )
    conversation.eval_result = result
    return result


async def evaluate_all(conversations: list[Conversation]) -> PersonaScores:
    """Evaluate all conversations and compute aggregate persona scores."""
    from core.archive import save_conversation

    # Evaluate sequentially to stay within rate limits (50 req/min, 30K tokens/min)
    for conv in conversations:
        await evaluate_conversation(conv)
        save_conversation(conv)  # Persist eval_result back to MongoDB

    # Group by persona
    by_persona: dict[str, list[Conversation]] = {}
    for conv in conversations:
        by_persona.setdefault(conv.persona_type, []).append(conv)

    per_persona: dict[str, MetricScores] = {}
    for persona in PERSONA_ARCHETYPES:
        convos = by_persona.get(persona, [])
        if not convos:
            per_persona[persona] = MetricScores(
                goal_completion=0, conversational_quality=1, compliance=0,
                response_consistency=0, sentiment_shift=0, weighted_total=0,
            )
            continue

        goals = [c.eval_result.goal_completion for c in convos]
        qualities = [c.eval_result.conversational_quality for c in convos]
        compliances = [c.eval_result.compliance for c in convos]
        consistencies = [c.eval_result.response_consistency for c in convos]
        sentiments = [c.eval_result.sentiment_shift for c in convos]
        totals = [c.eval_result.weighted_total for c in convos]

        per_persona[persona] = MetricScores(
            goal_completion=median(goals),
            conversational_quality=median(qualities),
            compliance=median(compliances),
            response_consistency=median(consistencies),
            sentiment_shift=median(sentiments),
            weighted_total=median(totals),
        )

    aggregate = mean(ps.weighted_total for ps in per_persona.values())
    scores = PersonaScores(per_persona=per_persona, aggregate=aggregate)

    logger.info(f"Aggregate score: {aggregate:.2f}")
    for p, s in per_persona.items():
        logger.info(
            f"  {p}: goal={s.goal_completion:.1f} quality={s.conversational_quality:.1f} "
            f"compliance={s.compliance:.1f} consistency={s.response_consistency:.1f} "
            f"sentiment={s.sentiment_shift:.2f} total={s.weighted_total:.2f}"
        )

    return scores
