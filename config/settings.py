"""All configuration constants for the evolution system."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")

# --- MongoDB ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:secret@localhost:27018/?authSource=admin")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "darwin_godel")

# --- Evolution Parameters ---
MAX_GENERATIONS = 5
SCORE_THRESHOLD = 4.0
PLATEAU_WINDOW = 3
PLATEAU_EPSILON = 0.1
CONVERSATIONS_PER_PERSONA = 2
MAX_TURNS_PER_CONVERSATION = 20

# --- Scoring Weights (V2: 5 metrics) ---
SCORING_WEIGHTS = {
    "goal_completion": 0.35,
    "conversational_quality": 0.15,
    "compliance": 0.30,
    "response_consistency": 0.10,
    "sentiment_shift": 0.10,
}

# --- Regression Guard ---
MAX_PERSONA_REGRESSION = 0.5

# --- Model Choices ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" | "anthropic" | "google"

if LLM_PROVIDER == "anthropic":
    SIMULATION_MODEL = "claude-sonnet-4-6"
    EVALUATION_MODEL = "claude-sonnet-4-6"
    ANALYSIS_MODEL = "claude-sonnet-4-6"
    MUTATION_MODEL = "claude-sonnet-4-6"
elif LLM_PROVIDER == "google":
    SIMULATION_MODEL = "gemini-3-flash-preview"
    EVALUATION_MODEL = "gemini-3-flash-preview"
    ANALYSIS_MODEL = "gemini-3-flash-preview"
    MUTATION_MODEL = "gemini-3-flash-preview"
else:
    SIMULATION_MODEL = "gpt-5.2"
    EVALUATION_MODEL = "gpt-5.2"
    ANALYSIS_MODEL = "gpt-5.2"
    MUTATION_MODEL = "gpt-5.2"

VOICE_MODEL = "gpt-4.1-mini"

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"
CONVERSATIONS_DIR = PROJECT_ROOT / "data" / "conversations"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"
BASE_PROMPT_PATH = PROJECT_ROOT / "prompts" / "base_v0.yaml"

# --- Persona Archetypes ---
PERSONA_ARCHETYPES = ["angry", "evasive", "hardship", "informed", "cooperative"]

# --- Immutable Section ---
IMMUTABLE_SECTIONS = {"compliance"}

# --- Prompt Sections ---
PROMPT_SECTIONS = ["identity", "objective", "compliance", "opening", "strategy", "closing"]
