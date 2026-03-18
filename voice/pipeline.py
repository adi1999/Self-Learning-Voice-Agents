"""Pipecat voice pipeline assembly with conversation logging."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

from config.settings import CARTESIA_API_KEY, DEEPGRAM_API_KEY, OPENAI_API_KEY, VOICE_MODEL
from core.models import AgentVersion, Conversation, ConversationMetadata, Turn
from core.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


class ConversationLoggerProcessor(FrameProcessor):
    """Captures turns from the voice pipeline for storage in MongoDB."""

    def __init__(self, version_id: str, **kwargs):
        super().__init__(**kwargs)
        self.version_id = version_id
        self.turns: list[Turn] = []
        self.turn_index = 0
        self._agent_text_buffer: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            # User speech transcription
            self.turns.append(Turn(
                index=self.turn_index,
                role="borrower",
                content=frame.text.strip(),
                timestamp=datetime.now(timezone.utc),
            ))
            self.turn_index += 1

        elif isinstance(frame, TextFrame) and frame.text.strip():
            # Accumulate agent response chunks
            self._agent_text_buffer.append(frame.text)

        if isinstance(frame, EndFrame):
            # Flush any remaining agent text
            self._flush_agent_buffer()
            self._save_conversation()

        await self.push_frame(frame, direction)

    def _flush_agent_buffer(self) -> None:
        """Flush accumulated agent text into a single turn."""
        if self._agent_text_buffer:
            full_text = "".join(self._agent_text_buffer).strip()
            if full_text:
                self.turns.append(Turn(
                    index=self.turn_index,
                    role="agent",
                    content=full_text,
                    timestamp=datetime.now(timezone.utc),
                ))
                self.turn_index += 1
            self._agent_text_buffer.clear()

    def _save_conversation(self) -> None:
        """Save the captured conversation to MongoDB."""
        if not self.turns:
            return
        try:
            from core.archive import save_conversation
            conv = Conversation(
                id=f"voice_{uuid4().hex[:8]}",
                agent_version_id=self.version_id,
                persona_type=None,
                persona_config=None,
                source="voice_live",
                turns=self.turns,
                outcome="ended_by_user",
                duration_turns=len(self.turns),
                metadata=ConversationMetadata(model_used=VOICE_MODEL),
            )
            save_conversation(conv)
            logger.info(f"Saved voice conversation {conv.id} ({len(self.turns)} turns)")
        except Exception:
            logger.error("Failed to save voice conversation", exc_info=True)


async def create_and_run_pipeline(
    agent_version: AgentVersion,
    transport,
    version_id: str | None = None,
) -> None:
    """Create and start the Pipecat voice pipeline in the background."""
    system_prompt = build_prompt(agent_version.prompt_sections)
    vid = version_id or agent_version.id

    context = OpenAILLMContext(
        messages=[{"role": "system", "content": system_prompt}]
    )

    llm = OpenAILLMService(api_key=OPENAI_API_KEY, model=VOICE_MODEL)
    context_aggregator = llm.create_context_aggregator(context)

    stt = DeepgramSTTService(api_key=DEEPGRAM_API_KEY)
    tts = CartesiaTTSService(
        api_key=CARTESIA_API_KEY,
        voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
    )

    conversation_logger = ConversationLoggerProcessor(version_id=vid)

    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
        conversation_logger,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True),
    )

    runner = PipelineRunner(handle_sigint=False)
    # Run in background so the callback returns immediately
    asyncio.create_task(runner.run(task))
