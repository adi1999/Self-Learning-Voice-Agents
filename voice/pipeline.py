"""Pipecat voice pipeline assembly with conversation logging."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    LLMContextFrame,
    LLMMessagesAppendFrame,
    TextFrame,
    UserIdleTimeoutUpdateFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)

from config.settings import (
    CARTESIA_API_KEY, DEEPGRAM_API_KEY, OPENAI_API_KEY, VOICE_MODEL, TTS_PROVIDER,
)
from core.models import AgentVersion, Conversation, ConversationMetadata, Turn
from core.prompt_builder import build_voice_prompt
from core.playbook import get_top_tactics

logger = logging.getLogger(__name__)


class EndCallMarkerProcessor(FrameProcessor):
    """Detects [END_CALL:reason] markers in streamed LLM output.

    The LLM streams token-by-token, so the marker is split across multiple
    TextFrames (e.g. "[", "END", "_CALL:", "goodbye", "]"). This processor
    buffers text when a "[" is seen, accumulates until the marker completes
    (or is ruled out), then strips the marker before TTS sees it.
    """

    _PATTERN = re.compile(r"\[END_CALL:(\w+)\]")
    # Matches any prefix of "[END_CALL:" that could still become the full marker
    _PARTIAL = re.compile(r"\[(?:E(?:N(?:D(?:_(?:C(?:A(?:L(?:L(?::(?:\w*)?)?)?)?)?)?)?)?)?)?$")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task: PipelineTask | None = None
        self._end_scheduled = False
        self.end_detected = False
        self._buffer = ""

    def set_task(self, task: PipelineTask) -> None:
        self._task = task

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame) and not self._end_scheduled:
            self._buffer += frame.text

            # Check for complete marker in the accumulated buffer
            match = self._PATTERN.search(self._buffer)
            if match:
                reason = match.group(1)
                cleaned = self._PATTERN.sub("", self._buffer).strip()
                self.end_detected = True
                self._end_scheduled = True
                self._buffer = ""
                logger.info(f"End-call marker detected — reason: {reason}")

                if cleaned:
                    await self.push_frame(TextFrame(text=cleaned), direction)

                await self.push_frame(
                    UserIdleTimeoutUpdateFrame(timeout=0), FrameDirection.UPSTREAM,
                )
                if self._task:
                    asyncio.create_task(self._end_after_grace(3.0))
                return

            # Check if the buffer tail could be the start of a marker
            bracket_pos = self._buffer.rfind("[")
            if bracket_pos == -1:
                # No "[" at all — flush everything to TTS immediately
                await self.push_frame(TextFrame(text=self._buffer), direction)
                self._buffer = ""
            else:
                tail = self._buffer[bracket_pos:]
                if self._PARTIAL.search(tail):
                    # Tail looks like an incomplete marker — hold it, flush the rest
                    safe = self._buffer[:bracket_pos]
                    self._buffer = tail
                    if safe:
                        await self.push_frame(TextFrame(text=safe), direction)
                else:
                    # "[" is present but not a valid marker prefix — flush all
                    await self.push_frame(TextFrame(text=self._buffer), direction)
                    self._buffer = ""
            return

        await self.push_frame(frame, direction)

    async def _end_after_grace(self, delay: float) -> None:
        """Wait for TTS to finish, then terminate the pipeline."""
        await asyncio.sleep(delay)
        if self._task:
            logger.info("Grace period elapsed — sending EndFrame")
            await self._task.queue_frame(EndFrame())


_END_CALL_RE = re.compile(r"\[END_CALL:\w+\]")


def _save_conversation_from_context(
    context: LLMContext, version_id: str,
) -> None:
    """Extract turns from the LLM context and save to MongoDB.

    The context already contains the full conversation (system, assistant,
    user messages) maintained by the aggregators. This is more reliable than
    trying to capture frames after TTS (which consumes TextFrames).
    """
    turns: list[Turn] = []
    turn_index = 0
    now = datetime.now(timezone.utc)

    for msg in context.messages:
        role_raw = msg.get("role", "")
        if role_raw == "system":
            continue
        content = msg.get("content", "")
        if not content or not content.strip():
            continue
        # Strip END_CALL markers from logged content
        content = _END_CALL_RE.sub("", content).strip()
        if not content:
            continue
        role = "agent" if role_raw == "assistant" else "borrower"
        turns.append(Turn(
            index=turn_index, role=role, content=content, timestamp=now,
        ))
        turn_index += 1

    if not turns:
        logger.warning("No turns captured — skipping conversation save")
        return

    try:
        from core.archive import save_conversation
        conv = Conversation(
            id=f"voice_{uuid4().hex[:8]}",
            agent_version_id=version_id,
            persona_type=None,
            persona_config=None,
            source="voice_live",
            turns=turns,
            outcome="ended_by_user",
            duration_turns=len(turns),
            metadata=ConversationMetadata(model_used=VOICE_MODEL),
        )
        save_conversation(conv)
        logger.info(f"Saved voice conversation {conv.id} ({len(turns)} turns)")
    except Exception:
        logger.error("Failed to save voice conversation", exc_info=True)


def _create_tts_service():
    """Create TTS service based on TTS_PROVIDER env var."""
    if TTS_PROVIDER == "cartesia":
        from pipecat.services.cartesia.tts import CartesiaTTSService
        return CartesiaTTSService(
            api_key=CARTESIA_API_KEY,
            voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
        )
    # Default: Deepgram TTS (uses same API key as STT)
    from pipecat.services.deepgram.tts import DeepgramTTSService
    return DeepgramTTSService(
        api_key=DEEPGRAM_API_KEY,
        voice="aura-2-orion-en",
    )


async def create_and_run_pipeline(
    agent_version: AgentVersion,
    transport,
    version_id: str | None = None,
) -> asyncio.Task:
    """Create and start the Pipecat voice pipeline in the background.

    Returns the background asyncio.Task so callers can cancel it on reconnect.
    """
    system_prompt = build_voice_prompt(agent_version.prompt_sections)
    vid = version_id or agent_version.id

    # Inject top tactics across all personas for the live voice agent
    from config.settings import MAX_TACTICS_PER_PROMPT
    tactics = get_top_tactics(limit=MAX_TACTICS_PER_PROMPT)
    if tactics:
        tactic_lines = "\n".join(f"- {t.tactic}" for t in tactics)
        system_prompt += f"\n\n## LEARNED TACTICS\nThese tactics have proven effective:\n{tactic_lines}"

    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt}],
    )

    llm = OpenAILLMService(api_key=OPENAI_API_KEY, model=VOICE_MODEL)

    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(user_idle_timeout=7.0),
    )

    stt = DeepgramSTTService(api_key=DEEPGRAM_API_KEY)
    tts = _create_tts_service()

    end_call_marker = EndCallMarkerProcessor()

    # --- Silence / idle follow-up handler ---
    user_aggregator = context_aggregator.user()

    idle_count = 0

    @user_aggregator.event_handler("on_user_turn_started")
    async def on_user_turn_started(aggregator, strategy):
        nonlocal idle_count
        idle_count = 0

    @user_aggregator.event_handler("on_user_turn_idle")
    async def on_user_turn_idle(aggregator):
        nonlocal idle_count
        if end_call_marker.end_detected:
            return
        idle_count += 1
        if idle_count >= 3:
            msg = (
                "The borrower has been silent for a long time after multiple check-ins. "
                "Politely wrap up the call, say goodbye, and include [END_CALL:no_response] "
                "at the end of your goodbye."
            )
        else:
            msg = (
                "The borrower has been quiet for several seconds. "
                "Gently check if they are still there or repeat your last question."
            )
        await aggregator.push_frame(
            LLMMessagesAppendFrame(
                messages=[{"role": "system", "content": msg}],
                run_llm=True,
            )
        )

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        end_call_marker,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True),
    )

    end_call_marker.set_task(task)

    # Trigger the initial greeting when the client connects
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await task.queue_frames([LLMContextFrame(context=context)])

    runner = PipelineRunner(handle_sigint=False)

    async def _run_with_cleanup():
        try:
            await runner.run(task)
        except asyncio.CancelledError:
            logger.info("Pipeline cancelled")
        finally:
            _save_conversation_from_context(context, vid)

    return asyncio.create_task(_run_with_cleanup())
