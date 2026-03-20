# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A platform that **automatically evolves** a debt collection voice agent through simulated conversations, automated evaluation, failure analysis, targeted prompt mutation, and persistent knowledge accumulation — without human intervention. The detailed system design is in `SYSTEM_DESIGN.md` (single source of truth for implementation).

The system has two layers of self-improvement:
1. **Prompt Evolution** — hill-climbing prompt rewriting that optimizes *what the agent says*
2. **Strategy Playbook** — persistent knowledge layer that extracts winning tactics from high-scoring conversations and records failed mutation approaches, optimizing *what the agent knows*

## Architecture

Three independent subsystems communicating through a shared data layer:

1. **Evolution Engine** (text-only): simulate conversations → evaluate with 5 judges → extract winning tactics → analyze failures (informed by cross-run tactics) → mutate one prompt section (with proven tactics + failed approaches from playbook) → select → record failures → repeat
2. **Voice Frontend**: Pipecat pipeline (SmallWebRTCTransport → DeepgramSTT → OpenAILLMService → CartesiaTTS) managed as a subprocess
3. **React Dashboard + FastAPI API**: React SPA (Vite + Tailwind) → FastAPI REST + SSE → core modules → MongoDB

**Independence guarantee**: Each subsystem runs standalone. Evolution doesn't need voice. Voice just reads a prompt version from the archive.

### Dependency Flow (strict, no circular deps)

```
config/          ← depends on nothing
core/            ← depends on config
simulation/      ← depends on core
evaluation/      ← depends on core
evolution/       ← depends on simulation, evaluation, core
voice/           ← depends on core (+ pipecat external)
api/             ← depends on core, simulation, evaluation, evolution, voice
frontend/        ← depends on api (HTTP only)
dashboard/       ← depends on core (HTML report generation only)
scripts/         ← depends on everything (thin CLI wrappers)
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `core/models.py` | Pydantic models: AgentVersion, Conversation, Turn, EvalResult, FailurePattern, StrategyTactic, FailedApproach, PersonaConfig |
| `core/archive.py` | Archive CRUD: save/load/query agent versions + conversations (MongoDB) |
| `core/prompt_builder.py` | Assembles 6 prompt sections into full prompt + `build_dynamic_prompt()` injects persona-specific tactics |
| `core/playbook.py` | MongoDB CRUD for strategy tactics and failed approaches |
| `core/llm_client.py` | Thin wrapper over LLM API calls — single place to swap models, handle retries, track costs |
| `config/personas.py` | 5 persona archetypes (angry, evasive, hardship, informed, cooperative) + randomization |
| `config/settings.py` | All config: API keys, thresholds, model choices, scoring weights, generation limits |
| `simulation/conversation.py` | Turn-by-turn ping-pong engine (agent LLM vs persona LLM) |
| `simulation/persona_runner.py` | Batch orchestrator: runs agent against all 5 personas in parallel |
| `evaluation/judges.py` | Five judges: GoalCompletion (0-3), Quality (1-5), Compliance (pass/fail), Consistency (pass/fail), Sentiment (-1 to +1) |
| `evaluation/scorer.py` | Aggregation: per-conversation weighted → per-persona median → aggregate mean |
| `evolution/failure_analyzer.py` | Top 3 failure patterns mapped to prompt sections, with turn-level examples |
| `evolution/mutator.py` | Targeted single-section rewrite, generates 2 candidates per mutation |
| `evolution/selector.py` | Regression-aware hill climbing (no persona drops > 0.5) |
| `evolution/tactic_extractor.py` | LLM-based extraction of winning tactics + failure recording after selection |
| `evolution/loop.py` | Full evolution loop orchestrator with termination conditions + playbook integration |
| `voice/pipeline.py` | Pipecat pipeline assembly using built-in OpenAILLMService + OpenAILLMContext |
| `voice/run_voice.py` | FastAPI server with WebRTC offer/answer + health endpoints |
| `api/main.py` | FastAPI app factory: lifespan, CORS, router registration |
| `api/tasks.py` | BackgroundTaskManager: async task registry, SSE subscriber queues |
| `api/routers/` | REST endpoints: versions, conversations, evolution, simulation, evaluation, voice, playbook, config |
| `api/services/` | Service layer bridging routers to core modules |
| `frontend/` | React SPA: Vite + TypeScript + Tailwind + Recharts |

## Prompt Architecture

The agent prompt is split into **6 sections**, each independently mutable:
- `identity`, `objective`, `compliance`, `opening`, `strategy`, `closing`
- **COMPLIANCE section is immutable** — never modified by the evolution loop (safety rail)
- Only one section is mutated per generation (Karpathy principle: change one variable at a time)
- Base prompt lives in `prompts/base_v0.yaml`

## Evolution Loop Algorithm

```
1. Load base prompt → create v0 → simulate → evaluate → extract tactics from high-scoring convos
2. Loop (max 5 generations):
   a. Analyze failures → top 3 patterns mapped to prompt sections (informed by cross-run tactics)
   b. Mutate highest-impact section → 2 candidate rewrites (with proven tactics + failed approaches from playbook)
   c. Simulate both candidates (20 convos total, with persona-specific tactics injected into prompt)
   d. Evaluate (5 judges × 20 convos = 100 judge calls)
   e. Extract tactics from high-scoring candidate conversations → save to playbook
   f. Select best non-regressing candidate → promote or keep parent
   g. Record failed candidates as FailedApproach → save to playbook
   h. Terminate if: score ≥ 4.0, or plateau (< 0.1 improvement for 3 gens), or budget hit
   i. On plateau: diversify by targeting an untouched section
3. Champion prompt + accumulated playbook tactics → plug into voice pipeline
```

## Strategy Playbook (Persistent Knowledge)

Tactics and failures persist in MongoDB across runs. Run 2 automatically benefits from run 1's knowledge.

- **Tactic extraction**: Conversations scoring ≥ 3.5 → LLM extracts 1-3 reusable tactics → deduplicated → saved to `strategy_tactics`
- **Failure recording**: Non-promoted candidates → rationale + score delta + persona regressions → saved to `failed_approaches`
- **Injection points**: simulation (per-persona tactics in prompt), failure analysis (cross-run context), mutation (proven tactics + anti-patterns), voice pipeline (top tactics across all personas)
- **Settings**: `TACTIC_SCORE_THRESHOLD = 3.5`, `MAX_TACTICS_PER_PROMPT = 5`

## Scoring

```
Per-conversation: goal(0.35) + quality(0.15) + compliance(0.30) + consistency(0.10) + sentiment(0.10)
  (all normalized to 0-1, then weighted, then scaled to 0-5)
Per-persona: median of N conversation scores
Aggregate: mean of per-persona scores
```

Compliance weight is 0.30 to prevent the optimizer from discovering "threatening works."

## Commands

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start FastAPI backend (port 8000)
python scripts/run_api.py

# Start React frontend dev server (port 3000, proxies /api to :8000)
cd frontend && npm install && npm run dev

# Production: build React and serve from FastAPI
cd frontend && npm run build
python scripts/run_api.py  # serves frontend/dist/ at /

# CLI scripts (still work independently)
python scripts/run_evolution.py --max-generations 5 --threshold 4.0
python scripts/run_simulation.py --version v0
python scripts/run_eval.py --version v0
python scripts/run_voice.py --version v5
python scripts/generate_report.py
```

## Environment

Requires `.env` file (see `.env.example`):
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` or `GOOGLE_API_KEY` — simulation, evaluation, failure analysis, mutation
- `DEEPGRAM_API_KEY` — STT (voice only)
- `CARTESIA_API_KEY` — TTS (voice only)
- `MONGO_URI` — MongoDB connection string
- `LLM_PROVIDER` — "openai" | "anthropic" | "google"

## Model Strategy

- Evolution (simulation, evaluation, analysis, mutation) uses the model set by `LLM_PROVIDER`
- Voice pipeline always uses `gpt-4.1-mini` (lowest latency for real-time)

## API Architecture

```
React (Vite SPA, port 3000)        ← dev proxy /api → localhost:8000
    ↓ REST + SSE
FastAPI (port 8000)
    ├── /api/versions/*            ← agent version CRUD
    ├── /api/conversations/*       ← conversation queries
    ├── /api/evolution/runs/*      ← start/stop/stream evolution
    ├── /api/simulation/*          ← trigger + stream transcripts
    ├── /api/evaluation/*          ← trigger evaluation
    ├── /api/voice/*               ← start/stop pipecat + WebRTC offer proxy
    ├── /api/playbook/*            ← accumulated tactics + failures
    └── /api/config                ← read-only settings
    ↓
core/ simulation/ evaluation/ evolution/  (domain logic)
    ↓
MongoDB (agent_versions, conversations, evolution_runs,
         strategy_tactics, failed_approaches)
```

### Backend Pattern

- **Routers** → **Services** → **core/** (proper separation)
- Services are stateless functions, not classes
- FastAPI `Depends()` for DI (task_manager)
- Long tasks (evolution, simulation) run as `asyncio.Task` via `BackgroundTaskManager`
- SSE streaming via subscriber queues for real-time progress
- Voice pipeline runs as subprocess on port 8001; offer proxied through main API

## Key Design Decisions

- **Sectioned prompts** — enables targeted mutation, controlled experiments, readable diffs
- **Hill-climbing with 2 candidates** — basic exploration at ~2× cost instead of N× for population-based
- **Regression detection** — prevents oscillation (improving one persona while regressing another)
- **Separate failure analysis from mutation** — diagnosis and prescription are different skills
- **Multiple conversations per persona** — median reduces LLM stochasticity noise
- **Immutable compliance section** — safety rail against optimizer gaming
- **Per-turn annotations** — gives failure analyzer surgical targets, not just holistic scores
- **Persistent playbook over stateless mutation** — prompt rewriting alone has no memory; the mutator repeats mistakes and loses winning tactics across runs
- **Per-persona tactic injection** — different personas need different tactics; a de-escalation tactic for angry borrowers hurts with cooperative ones
- **Failed approach recording** — negative knowledge is as valuable as positive; prevents trying the same mutation twice
- **Text simulation first, voice last** — evolution loop is 95% of intellectual content; voice is presentation layer
- **React + FastAPI over Streamlit** — proper API layer, embeddable WebRTC, production-ready

## Data Layout

```
data/
├── archive/           # Exported JSON (from export_json.py)
├── conversations/     # Exported conversation logs
└── reports/           # Generated HTML reports
```

Primary data lives in MongoDB (collections: `agent_versions`, `conversations`, `evolution_runs`, `strategy_tactics`, `failed_approaches`).

## Code Conventions

- **File size hard limit: 400 lines** — split by responsibility before hitting this
- Every function does ONE thing; split if doing two
- Move deterministic pure functions to utils with a one-line comment stating what it does and where it's used
- Check for existing implementations before writing new code — extend, don't duplicate
