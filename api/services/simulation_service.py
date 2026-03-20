"""Service bridging simulation/conversation.py to BackgroundTaskManager + SSE."""

import logging

from api.tasks import BackgroundTaskManager
from config.personas import randomize_persona
from core.archive import load_version, save_conversation
from core.models import Turn
from core.prompt_builder import build_prompt
from simulation.conversation import simulate_conversation

logger = logging.getLogger(__name__)


async def start_simulation(
    task_manager: BackgroundTaskManager,
    task_id: str,
    version_id: str,
    persona: str,
    evaluate: bool,
) -> None:
    async def _run():
        agent_version = load_version(version_id)
        agent_prompt = build_prompt(agent_version.prompt_sections)
        persona_config = randomize_persona(persona)

        def on_turn(turn: Turn) -> None:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(task_manager.broadcast(task_id, {
                    "event": "turn",
                    "data": {
                        "turn_index": turn.index,
                        "role": turn.role,
                        "content": turn.content,
                    },
                }))
            except RuntimeError:
                pass

        conversation = await simulate_conversation(
            agent_prompt=agent_prompt,
            persona_config=persona_config,
            version_id=version_id,
            run_number=999,
            on_turn=on_turn,
        )

        if evaluate:
            from evaluation.scorer import evaluate_conversation
            await evaluate_conversation(conversation)

        save_conversation(conversation)
        return conversation.id

    await task_manager.start_task(task_id, _run())
