"""Regression-aware hill climbing selection."""

import logging

from config.settings import MAX_PERSONA_REGRESSION, PERSONA_ARCHETYPES
from core.models import AgentVersion

logger = logging.getLogger(__name__)


def select_champion(
    parent: AgentVersion,
    candidates: list[AgentVersion],
    max_regression: float = MAX_PERSONA_REGRESSION,
) -> AgentVersion | None:
    """Select the best candidate that beats the parent without per-persona regression.

    Returns the promoted candidate, or None if no candidate qualifies.
    """
    if not parent.scores:
        logger.warning("Parent has no scores — cannot compare")
        return None

    best: AgentVersion | None = None

    for candidate in candidates:
        if not candidate.scores:
            logger.debug(f"Skipping {candidate.id}: no scores")
            continue

        # Must improve aggregate score
        if candidate.scores.aggregate <= parent.scores.aggregate:
            logger.debug(
                f"Skipping {candidate.id}: aggregate {candidate.scores.aggregate:.2f} "
                f"<= parent {parent.scores.aggregate:.2f}"
            )
            continue

        # Check per-persona regression
        regressed = False
        for persona in PERSONA_ARCHETYPES:
            parent_score = parent.scores.per_persona[persona].weighted_total
            child_score = candidate.scores.per_persona[persona].weighted_total
            if parent_score - child_score > max_regression:
                logger.debug(
                    f"Skipping {candidate.id}: {persona} regressed "
                    f"{parent_score:.2f} → {child_score:.2f} (>{max_regression})"
                )
                regressed = True
                break

        if not regressed:
            if best is None or candidate.scores.aggregate > best.scores.aggregate:
                best = candidate

    if best:
        logger.info(
            f"Selected {best.id} (aggregate {best.scores.aggregate:.2f}) "
            f"over parent {parent.id} ({parent.scores.aggregate:.2f})"
        )
    else:
        logger.info(f"No candidate beat parent {parent.id} without regression — keeping champion")

    return best
