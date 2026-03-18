"""Turn-by-turn ping-pong simulation engine."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from config.settings import MAX_TURNS_PER_CONVERSATION, SIMULATION_MODEL
from core.llm_client import llm_call, token_counter
from core.models import Conversation, ConversationMetadata, PersonaConfig, Turn
from config.personas import build_persona_prompt
from simulation.termination import check_termination, strip_termination_signal

logger = logging.getLogger(__name__)


async def simulate_conversation(
    agent_prompt: str,
    persona_config: PersonaConfig,
    version_id: str,
    run_number: int,
    max_turns: int = MAX_TURNS_PER_CONVERSATION,
    on_turn: Callable[[Turn], None] | None = None,
) -> Conversation:
    """Run a full simulated conversation between agent and persona LLMs."""
    persona_prompt = build_persona_prompt(persona_config)
    agent_history: list[dict] = []
    persona_history: list[dict] = []
    turns: list[Turn] = []
    outcome = "timeout"
    conv_id = f"{version_id}_{persona_config.archetype}_{run_number:03d}"
    tc = token_counter()
    tc.__enter__()

    # Agent opens the call (Anthropic API requires at least one message)
    agent_response = await llm_call(
        system=agent_prompt,
        messages=[{"role": "user", "content": f"[The phone is ringing. You are calling {persona_config.name} about their overdue loan. Open the call.]"}],
        model=SIMULATION_MODEL,
    )
    agent_history.append({"role": "assistant", "content": agent_response})
    persona_history.append({"role": "user", "content": agent_response})
    turn = Turn(index=0, role="agent", content=agent_response, timestamp=datetime.now(timezone.utc))
    turns.append(turn)
    if on_turn:
        on_turn(turn)

    turn_idx = 1
    for _ in range(1, max_turns):
        # Persona responds
        persona_response = await llm_call(
            system=persona_prompt,
            messages=persona_history,
            model=SIMULATION_MODEL,
        )
        detected_outcome = check_termination(persona_response)
        clean_response = strip_termination_signal(persona_response)

        persona_history.append({"role": "assistant", "content": clean_response})
        agent_history.append({"role": "user", "content": clean_response})
        turn = Turn(index=turn_idx, role="borrower", content=clean_response, timestamp=datetime.now(timezone.utc))
        turns.append(turn)
        if on_turn:
            on_turn(turn)
        turn_idx += 1

        if detected_outcome:
            outcome = detected_outcome
            break

        # Agent responds
        agent_response = await llm_call(
            system=agent_prompt,
            messages=agent_history,
            model=SIMULATION_MODEL,
        )
        detected_outcome = check_termination(agent_response)
        clean_response = strip_termination_signal(agent_response)

        agent_history.append({"role": "assistant", "content": clean_response})
        persona_history.append({"role": "user", "content": clean_response})
        turn = Turn(index=turn_idx, role="agent", content=clean_response, timestamp=datetime.now(timezone.utc))
        turns.append(turn)
        if on_turn:
            on_turn(turn)
        turn_idx += 1

        if detected_outcome:
            outcome = detected_outcome
            break

    tc.__exit__(None, None, None)
    logger.info(f"Conversation {conv_id}: {len(turns)} turns, outcome={outcome}, tokens={tc.total_tokens}")

    return Conversation(
        id=conv_id,
        agent_version_id=version_id,
        persona_type=persona_config.archetype,
        persona_config=persona_config,
        source="simulation",
        turns=turns,
        outcome=outcome,
        duration_turns=len(turns),
        metadata=ConversationMetadata(
            model_used=SIMULATION_MODEL,
            total_tokens=tc.total_tokens,
        ),
    )
