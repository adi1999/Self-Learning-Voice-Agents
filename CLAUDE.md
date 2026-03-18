# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A platform that **automatically evolves** a debt collection voice agent's prompts through simulated conversations, automated evaluation, failure analysis, and targeted prompt mutation — without human intervention. The detailed system design is in `SYSTEM_DESIGN.md` (single source of truth for implementation).

## Architecture

Three independent subsystems communicating through a shared data layer:

1. **Evolution Engine** (text-only): simulate conversations → evaluate with 3 judges → analyze failures → mutate one prompt section → repeat
2. **Voice Frontend**: Pipecat pipeline (SmallWebRTCTransport → DeepgramSTT → OpenAILLMService → CartesiaTTS) served via FastAPI + WebRTC
3. **Dashboard**: HTML report with evolution tree, score charts, prompt diffs

**Independence guarantee**: Each subsystem runs standalone. Evolution doesn't need voice. Voice just reads a prompt version from the archive.

### Dependency Flow (strict, no circular deps)

```
config/          ← depends on nothing
core/            ← depends on config
simulation/      ← depends on core
evaluation/      ← depends on core
evolution/       ← depends on simulation, evaluation, core
voice/           ← depends on core (+ pipecat external)
dashboard/       ← depends on core
scripts/         ← depends on everything (thin CLI wrappers)
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `core/models.py` | Pydantic models: AgentVersion, Conversation, Turn, EvalResult, FailurePattern, PersonaConfig |
| `core/archive.py` | Archive CRUD: save/load/query agent versions + conversations (JSON files in `data/`) |
| `core/prompt_builder.py` | Assembles 6 prompt sections (identity, objective, compliance, opening, strategy, closing) into full prompt |
| `core/llm_client.py` | Thin wrapper over LLM API calls — single place to swap models, handle retries, track costs |
| `config/personas.py` | 5 persona archetypes (angry, evasive, hardship, informed, cooperative) + randomization |
| `config/settings.py` | All config: API keys, thresholds, model choices, scoring weights, generation limits |
| `simulation/conversation.py` | Turn-by-turn ping-pong engine (agent LLM vs persona LLM) |
| `simulation/persona_runner.py` | Batch orchestrator: runs agent against all 5 personas in parallel |
| `evaluation/judges.py` | Three judges: GoalCompletionJudge (0-3), ConversationalQualityJudge (1-5), ComplianceJudge (pass/fail) |
| `evaluation/scorer.py` | Aggregation: per-conversation weighted → per-persona median → aggregate mean |
| `evolution/failure_analyzer.py` | Top 3 failure patterns mapped to prompt sections, with turn-level examples |
| `evolution/mutator.py` | Targeted single-section rewrite, generates 2 candidates per mutation |
| `evolution/selector.py` | Regression-aware hill climbing (no persona drops > 0.5) |
| `evolution/loop.py` | Full evolution loop orchestrator with termination conditions |
| `voice/pipeline.py` | Pipecat pipeline assembly using built-in OpenAILLMService + OpenAILLMContext |
| `voice/run_voice.py` | FastAPI server with WebRTC offer/answer endpoints |

## Prompt Architecture

The agent prompt is split into **6 sections**, each independently mutable:
- `identity`, `objective`, `compliance`, `opening`, `strategy`, `closing`
- **COMPLIANCE section is immutable** — never modified by the evolution loop (safety rail)
- Only one section is mutated per generation (Karpathy principle: change one variable at a time)
- Base prompt lives in `prompts/base_v0.yaml`

## Evolution Loop Algorithm

```
1. Load base prompt → create v0 → evaluate (5 personas × 3 conversations = 15 convos)
2. Loop (max 10 generations):
   a. Analyze failures → top 3 patterns mapped to prompt sections
   b. Mutate highest-impact section → 2 candidate rewrites
   c. Simulate both candidates (30 convos total)
   d. Evaluate (3 judges × 30 convos = 90 judge calls)
   e. Select best non-regressing candidate → promote or keep parent
   f. Terminate if: score ≥ 4.0, or plateau (< 0.1 improvement for 3 gens), or budget hit
   g. On plateau: diversify by targeting an untouched section
3. Champion prompt → plug into voice pipeline
```

## Scoring

```
Per-conversation: goal_completion × 0.5 + conversational_quality × 0.1 + compliance × 0.4
Per-persona: median of N conversation scores
Aggregate: mean of per-persona scores
```

Compliance weight is 0.4 to prevent the optimizer from discovering "threatening works."

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full evolution loop
python scripts/run_evolution.py --max-generations 10 --threshold 4.0 --conversations-per-persona 3

# Simulate a single version (debugging)
python scripts/run_simulation.py --version v0

# Re-evaluate existing conversation logs
python scripts/run_eval.py --version v0

# Start voice agent with a specific prompt version
python scripts/run_voice.py --version v5
# Opens browser at http://localhost:8000

# Generate HTML evolution report
python scripts/generate_report.py
# Outputs: data/reports/evolution_report.html
```

## Environment

Requires `.env` file (see `.env.example`):
- `ANTHROPIC_API_KEY` — simulation, evaluation, failure analysis, mutation
- `OPENAI_API_KEY` — voice pipeline LLM (lowest latency for real-time)
- `DEEPGRAM_API_KEY` — STT
- `CARTESIA_API_KEY` — TTS

## Model Strategy

- `claude-sonnet-4-6` for simulation, evaluation, analysis, and mutation (all text-based evolution work)
- `gpt-5.4-mini` for voice pipeline only (lowest latency for real-time)

## Key Design Decisions

- **Sectioned prompts** — enables targeted mutation, controlled experiments, readable diffs
- **Hill-climbing with 2 candidates** — basic exploration at ~2× cost instead of N× for population-based
- **Regression detection** — prevents oscillation (improving one persona while regressing another)
- **Separate failure analysis from mutation** — diagnosis and prescription are different skills
- **3 conversations per persona** — median of 3 reduces LLM stochasticity noise
- **Immutable compliance section** — safety rail against optimizer gaming
- **Per-turn annotations** — gives failure analyzer surgical targets, not just holistic scores
- **Text simulation first, voice last** — evolution loop is 95% of intellectual content; voice is presentation layer

## Data Layout

```
data/
├── archive/           # One JSON per agent version (v0.json, v1.json, ...)
├── conversations/     # Raw conversation logs (v0_angry_001.json, ...)
└── reports/           # Generated HTML reports
```

## Code Conventions

- **File size hard limit: 400 lines** — split by responsibility before hitting this
- Every function does ONE thing; split if doing two
- Move deterministic pure functions to utils with a one-line comment stating what it does and where it's used
- Check for existing implementations before writing new code — extend, don't duplicate
