"""Batch orchestrator: runs agent against all personas in parallel."""

import asyncio
import logging

from config.personas import randomize_persona
from config.settings import CONVERSATIONS_PER_PERSONA, PERSONA_ARCHETYPES
from core.models import AgentVersion, Conversation
from core.prompt_builder import build_prompt
from simulation.conversation import simulate_conversation

logger = logging.getLogger(__name__)


async def run_full_evaluation_suite(
    agent_version: AgentVersion,
    conversations_per_persona: int = CONVERSATIONS_PER_PERSONA,
) -> list[Conversation]:
    """Run agent against all 5 personas, N conversations each — in parallel."""
    agent_prompt = build_prompt(agent_version.prompt_sections)

    tasks = []
    for archetype in PERSONA_ARCHETYPES:
        for run in range(conversations_per_persona):
            persona_config = randomize_persona(archetype)
            tasks.append(
                simulate_conversation(
                    agent_prompt=agent_prompt,
                    persona_config=persona_config,
                    version_id=agent_version.id,
                    run_number=run + 1,
                )
            )

    total = len(tasks)
    logger.info(f"Starting {total} conversations for {agent_version.id}...")
    conversations = await asyncio.gather(*tasks)
    logger.info(f"Completed {total} conversations for {agent_version.id}")
    return list(conversations)
