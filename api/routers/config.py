"""Read-only config endpoint."""

from fastapi import APIRouter

from config.settings import (
    CONVERSATIONS_PER_PERSONA,
    IMMUTABLE_SECTIONS,
    MAX_GENERATIONS,
    MAX_TURNS_PER_CONVERSATION,
    PERSONA_ARCHETYPES,
    PLATEAU_EPSILON,
    PLATEAU_WINDOW,
    PROMPT_SECTIONS,
    SCORE_THRESHOLD,
    SCORING_WEIGHTS,
    SIMULATION_MODEL,
    EVALUATION_MODEL,
    VOICE_MODEL,
    LLM_PROVIDER,
)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/")
def get_config():
    return {
        "max_generations": MAX_GENERATIONS,
        "score_threshold": SCORE_THRESHOLD,
        "conversations_per_persona": CONVERSATIONS_PER_PERSONA,
        "max_turns_per_conversation": MAX_TURNS_PER_CONVERSATION,
        "plateau_window": PLATEAU_WINDOW,
        "plateau_epsilon": PLATEAU_EPSILON,
        "scoring_weights": SCORING_WEIGHTS,
        "persona_archetypes": PERSONA_ARCHETYPES,
        "prompt_sections": PROMPT_SECTIONS,
        "immutable_sections": list(IMMUTABLE_SECTIONS),
        "llm_provider": LLM_PROVIDER,
        "simulation_model": SIMULATION_MODEL,
        "evaluation_model": EVALUATION_MODEL,
        "voice_model": VOICE_MODEL,
    }
