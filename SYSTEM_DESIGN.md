# System Design Document

> **Purpose**: Single source of truth for the self-evolving debt collection voice agent. Covers architecture, data models, module responsibilities, and implementation details.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Directory Structure](#2-directory-structure)
3. [Core Data Models](#3-core-data-models)
4. [Prompt Architecture](#4-prompt-architecture)
5. [Persona Design](#5-persona-design)
6. [Simulation Engine](#6-simulation-engine)
7. [Evaluation System](#7-evaluation-system)
8. [Failure Analysis](#8-failure-analysis)
9. [Mutation Strategy](#9-mutation-strategy)
10. [Selection & Promotion](#10-selection--promotion)
11. [Evolution Loop Orchestration](#11-evolution-loop-orchestration)
12. [Strategy Playbook (Persistent Knowledge)](#12-strategy-playbook-persistent-knowledge)
13. [Pipecat Voice Pipeline](#13-pipecat-voice-pipeline)
14. [FastAPI Backend](#14-fastapi-backend)
15. [React Frontend](#15-react-frontend)
16. [Configuration & Environment](#16-configuration--environment)
17. [Key Design Decisions](#17-key-design-decisions)

---

## 1. Architecture Overview

Three independent subsystems communicating through MongoDB:

```
┌─────────────────────────────────────────────────────┐
│                  MONGODB (shared data)               │
│  agent_versions · conversations · evolution_runs      │
│  strategy_tactics · failed_approaches                 │
└──────────┬──────────────┬──────────────┬────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────────┐
    │  EVOLUTION  │ │   VOICE    │ │ REACT + API  │
    │   ENGINE    │ │  PIPELINE  │ │  DASHBOARD   │
    └─────────────┘ └────────────┘ └──────────────┘
```

**Independence guarantee**: Each subsystem runs standalone.
- Evolution engine runs text-only simulations — no voice dependency
- Voice pipeline reads a prompt version from the archive + top tactics from the playbook — no evolution dependency
- React dashboard reads/writes via FastAPI API — no direct dependency on either

**Two layers of self-improvement**:
1. **Prompt Evolution** — hill-climbing prompt rewriting (optimizes *what the agent says*)
2. **Strategy Playbook** — persistent knowledge that accumulates across generations and across runs (optimizes *what the agent knows*)

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

---

## 2. Directory Structure

```
├── config/
│   ├── settings.py                 # All config: API keys, thresholds, weights, model choices
│   └── personas.py                 # 5 persona archetypes + randomization (Indian context)
├── core/
│   ├── models.py                   # Pydantic models: AgentVersion, Conversation, EvalResult, etc.
│   ├── db.py                       # MongoDB connection + collection references
│   ├── archive.py                  # Archive CRUD (agent versions, conversations, evolution runs)
│   ├── prompt_builder.py           # Assembles 6 sections → full system prompt + dynamic prompt with tactics
│   ├── playbook.py                # MongoDB CRUD for strategy tactics + failed approaches
│   └── llm_client.py              # LLM wrapper: OpenAI / Anthropic / Google, retries, cost tracking
├── simulation/
│   ├── conversation.py             # Turn-by-turn ping-pong engine (agent LLM ↔ persona LLM)
│   ├── persona_runner.py           # Batch orchestrator: all personas in parallel
│   └── termination.py             # End-of-conversation detection ([END:reason] signals)
├── evaluation/
│   ├── judges.py                   # 5 judges: goal, quality, compliance, consistency, sentiment
│   ├── scorer.py                   # Score aggregation: per-conversation → per-persona → aggregate
│   └── annotator.py               # Per-turn annotation extraction
├── evolution/
│   ├── failure_analyzer.py         # Top 3 failure patterns → target prompt section (informed by cross-run tactics)
│   ├── mutator.py                  # Targeted single-section rewrite (2 candidates, with playbook context)
│   ├── selector.py                 # Regression-aware hill climbing
│   ├── tactic_extractor.py        # LLM-based extraction of winning tactics + failure recording
│   └── loop.py                     # Full evolution loop orchestrator + playbook integration
├── voice/
│   ├── pipeline.py                 # Pipecat: SmallWebRTCTransport + OpenAILLMService + ConversationLogger
│   └── run_voice.py               # FastAPI server with WebRTC signaling + health endpoint
├── api/
│   ├── main.py                     # App factory: lifespan, CORS, router registration
│   ├── dependencies.py             # DI: get_task_manager()
│   ├── exceptions.py               # Custom exceptions + global handlers (NotFound → 404, etc.)
│   ├── tasks.py                    # BackgroundTaskManager: task registry, SSE subscriber queues
│   ├── schemas/                    # Pydantic request/response models
│   │   ├── common.py               # ErrorResponse, TaskResponse
│   │   ├── versions.py             # AgentVersionSummary
│   │   ├── conversations.py        # ConversationSummary, ConversationFilters
│   │   ├── evolution.py            # StartEvolutionRequest, EvolutionProgress
│   │   ├── simulation.py           # SimulateRequest, SimulationProgress
│   │   └── evaluation.py           # EvaluateRequest
│   ├── routers/                    # REST endpoint definitions
│   │   ├── versions.py             # GET /, GET /{id}, GET /champion
│   │   ├── conversations.py        # GET / (filtered), GET /{id}
│   │   ├── evolution.py            # GET/POST /runs, GET /runs/{id}/stream, DELETE /runs/{id}
│   │   ├── simulation.py           # POST /, GET /{id}/stream
│   │   ├── evaluation.py           # POST /
│   │   ├── voice.py                # GET /status, POST /start, POST /stop, POST /offer
│   │   ├── playbook.py             # GET /tactics, GET /tactics/{persona}, GET /failures, GET /stats
│   │   └── config.py               # GET /
│   └── services/                   # Stateless service functions bridging routers → core
│       ├── version_service.py      # Wraps core/archive.py version functions
│       ├── conversation_service.py # Wraps core/archive.py conversation functions
│       ├── evolution_service.py    # Bridges evolution/loop.py → BackgroundTaskManager + SSE
│       ├── simulation_service.py   # Bridges simulation/conversation.py → SSE
│       ├── evaluation_service.py   # Wraps evaluation judges + save
│       ├── voice_service.py        # Manages pipecat subprocess lifecycle (start/stop/health poll)
│       └── playbook_service.py    # Wraps core/playbook.py for API layer
├── frontend/
│   ├── vite.config.ts              # Proxy /api → localhost:8000
│   └── src/
│       ├── App.tsx                  # React Router, 6 routes
│       ├── api/client.ts           # Typed fetch wrappers for all endpoints
│       ├── hooks/useSSE.ts         # Custom hook wrapping EventSource
│       ├── pages/
│       │   ├── Personas.tsx         # 5 cards, simulate, live transcript, eval scores
│       │   ├── Evolution.tsx        # Config form, start, SSE progress log, score chart
│       │   ├── Conversations.tsx    # Filters + expandable table with transcripts
│       │   ├── Archive.tsx          # Version list, prompt diffs, per-persona scores
│       │   ├── VoiceAgent.tsx       # Start/stop server, native WebRTC call, history
│       │   └── Playbook.tsx        # Accumulated tactics + failures, stats by persona/section
│       └── components/
│           ├── Layout.tsx           # Sidebar nav + content area
│           ├── PersonaCard.tsx      # Single persona card
│           ├── TranscriptView.tsx   # Turn-by-turn chat display with annotations
│           ├── EvalBreakdown.tsx    # 5-metric score table
│           ├── ScoreChart.tsx       # Recharts line chart (aggregate + per-persona)
│           ├── PromptDiff.tsx       # Side-by-side before/after diff
│           ├── ProgressLog.tsx      # Auto-scrolling SSE-fed terminal log
│           └── VersionSelector.tsx  # Reusable version dropdown
├── dashboard/
│   ├── report_generator.py         # Static HTML report orchestration
│   ├── score_charts.py            # Score visualization
│   ├── tree_visualizer.py          # Mermaid evolution tree diagram
│   └── diff_viewer.py             # Prompt diffs between versions
├── prompts/
│   └── base_v0.yaml               # Handcrafted seed prompt (6 sections, Indian NBFC context)
├── scripts/
│   ├── run_api.py                  # CLI: start FastAPI server (uvicorn)
│   ├── run_evolution.py            # CLI: full evolution loop
│   ├── run_simulation.py           # CLI: simulate one version
│   ├── run_eval.py                 # CLI: evaluate conversations
│   ├── run_voice.py               # CLI: start voice agent (standalone)
│   ├── generate_report.py         # CLI: generate HTML report
│   └── export_json.py             # CLI: dump MongoDB → JSON
└── data/                           # Exported JSON data
    ├── archive/
    ├── conversations/
    └── reports/
```

---

## 3. Core Data Models

All models live in `core/models.py` using Pydantic.

### AgentVersion

```python
class AgentVersion(BaseModel):
    id: str                                    # "v0", "run123_v1a", ...
    run_id: str | None                         # Evolution run this belongs to
    parent_id: str | None                      # None for base version
    generation: int                            # 0 for base, increments each generation
    prompt_sections: dict[str, str]            # Keys: identity, objective, compliance,
                                               #        opening, strategy, closing
    mutation_target: str | None                # Which section was changed (None for base)
    rationale: str | None                      # Why this mutation was made
    failure_patterns: list[str]                # Which failure patterns motivated this
    scores: PersonaScores | None               # None until evaluated
    status: Literal["base", "promoted", "archived"]
    created_at: datetime
```

### PersonaScores

```python
class PersonaScores(BaseModel):
    per_persona: dict[str, MetricScores]       # {"angry": MetricScores, "evasive": ...}
    aggregate: float                           # Weighted overall score (0-5)

class MetricScores(BaseModel):
    goal_completion: float                     # 0-3
    conversational_quality: float              # 1.0-5.0
    compliance: float                          # 0.0 or 1.0
    response_consistency: float                # 0.0 or 1.0
    sentiment_shift: float                     # -1.0 to +1.0
    weighted_total: float
```

### Conversation

```python
class Conversation(BaseModel):
    id: str
    agent_version_id: str
    persona_type: str | None                   # None for live voice conversations
    persona_config: PersonaConfig | None
    source: Literal["simulation", "voice_live"]
    turns: list[Turn]
    outcome: Literal["success", "rejection", "hallucination", "timeout", "ended_by_user"]
    duration_turns: int
    eval_result: EvalResult | None
    metadata: ConversationMetadata
    created_at: datetime

class Turn(BaseModel):
    index: int
    role: Literal["agent", "borrower"]
    content: str
    timestamp: datetime | None = None
    annotations: list[TurnAnnotation] = []

class PersonaConfig(BaseModel):
    archetype: str                             # "angry", "evasive", etc.
    name: str                                  # Randomized Indian name
    loan_amount: float                         # ₹25,000–₹5,00,000
    months_overdue: int                        # 2-18
    backstory: str                             # Randomized snippet
```

### EvalResult

```python
class EvalResult(BaseModel):
    goal_completion: float                     # 0-3
    conversational_quality: float              # 1-5
    compliance: float                          # 0 or 1
    response_consistency: float                # 0 or 1 (pass/fail)
    sentiment_shift: float                     # -1.0 to +1.0
    weighted_total: float
    turn_annotations: list[TurnAnnotation]
    hallucinations_found: list[str]
    tone_assessment: str
    consistency_issues: list[str]
```

### FailurePattern

```python
class FailurePattern(BaseModel):
    description: str                           # One-sentence description
    target_section: str                        # Which prompt section is responsible
    example_turns: list[TurnReference]         # Specific turn references
    suggested_direction: str                   # Direction of fix (not the fix itself)
```

### StrategyTactic (Playbook)

```python
class StrategyTactic(BaseModel):
    id: str                                    # "tactic_{uuid8}"
    persona_type: str                          # "angry", "evasive", etc.
    prompt_section: str                        # Which section this relates to
    tactic: str                                # 1-3 sentence description of what worked
    example_turns: list[TurnReference]
    score_impact: float                        # weighted_total of source conversation
    source_version_id: str
    source_run_id: str | None
    created_at: datetime
```

### FailedApproach (Playbook)

```python
class FailedApproach(BaseModel):
    id: str                                    # "fail_{uuid8}"
    target_section: str                        # Which section was mutated
    description: str                           # What was tried (from candidate.rationale)
    failure_reason: Literal["no_improvement", "regression", "not_selected"]
    parent_version_id: str
    candidate_version_id: str
    score_before: float
    score_after: float
    persona_regressions: dict[str, float]      # persona -> score delta (negative)
    source_run_id: str | None
    created_at: datetime
```

MongoDB collections `strategy_tactics` and `failed_approaches` are append-only — they accumulate knowledge across runs.

---

## 4. Prompt Architecture

### Sectioned Design

The agent prompt is split into 6 sections, each independently mutable:

| Section | Responsibility | Mutable? |
|---------|---------------|----------|
| `identity` | Who the agent is (Arjun at Riverline Financial Services) | Yes |
| `objective` | Goals and acceptable outcomes hierarchy | Yes |
| `compliance` | Hard rules — RBI Fair Practices Code, NBFC regulations | **No — immutable** |
| `opening` | How to start the call, identity verification | Yes |
| `strategy` | Objection handling per borrower type | Yes |
| `closing` | Commitment-securing, summarization, follow-up | Yes |

### Why This Split

- Each section maps to a **distinct failure mode** → enables targeted mutation
- COMPLIANCE is **immutable** — prevents the optimizer from discovering "threatening works"
- Sections are independently evaluable
- Prompt diffs between versions are readable (only one section changes per generation)

### Prompt Assembly

`core/prompt_builder.py` provides two assembly modes:

- **`build_prompt(sections)`** — Static assembly: concatenates sections with markdown headers. Used as the base for all prompts.
- **`build_dynamic_prompt(sections, persona_type)`** — Dynamic assembly: starts with `build_prompt`, then queries the playbook for the top 5 tactics matching the persona type and appends a `## LEARNED TACTICS` section. Used during simulation and by the voice pipeline.

This means the agent's live behavior reflects accumulated knowledge from all previous runs, not just the static prompt text.

---

## 5. Persona Design

### 5 Archetypes (Indian Context)

Defined in `config/personas.py`. Indian names, Rs. amounts, EMI terminology, NBFC/RBI references.

| Archetype | Behavior Pattern | Tests Agent's Ability To... |
|-----------|-----------------|----------------------------|
| **ANGRY** | Hostile, threatens RBI complaint, questions legitimacy | De-escalate, maintain composure, keep compliance |
| **EVASIVE** | Dodges questions, "salary hasn't come", keeps postponing | Create urgency, redirect, persist without annoying |
| **HARDSHIP** | Lost IT job, medical emergency, genuinely can't pay | Show empathy, offer alternatives, pivot to options |
| **INFORMED** | Cites RBI guidelines, SARFAESI Act, knows legal rights | Handle legal questions, offer validation, stay accurate |
| **COOPERATIVE** | Willing to pay, asks about EMI options, reasonable | Close efficiently, offer specific plans (ceiling detector) |

### Randomization

Each conversation gets randomized surface details to prevent overfitting (name, loan amount, months overdue, backstory).

### COOPERATIVE as Ceiling Detector

If the agent can't close a cooperative borrower, the base prompt is fundamentally broken — the issue isn't objection handling but core conversational ability.

---

## 6. Simulation Engine

### Turn-by-Turn Ping-Pong

`simulation/conversation.py` runs a two-party conversation where each side maintains its own message history. The agent sees persona messages as "user" messages and vice versa.

### Termination Detection

`simulation/termination.py`: Parse `[END:reason]` signals. Valid reasons: `agreed_to_pay`, `hung_up`, `asked_to_stop`, `callback_agreed`. Hard cap: 20 turns.

### Batch Orchestration

`simulation/persona_runner.py` runs all 5 personas × N conversations in parallel using `asyncio.gather`. Each persona's conversations use `build_dynamic_prompt()` to inject persona-specific tactics from the playbook into the agent's system prompt.

### Token Usage

Both the simulation engine and the voice pipeline use stateless LLM APIs. The **full conversation history is resent with every turn** — there is no server-side session. In a 20-turn conversation, turn 20's API call includes turns 1–19 plus the system prompt. This is the standard approach for Chat Completions-style APIs. Possible optimizations include sliding-window context, periodic summarization, or leveraging provider-side prompt caching.

### Live UI Updates

`simulate_conversation` accepts an optional `on_turn` callback. The API service layer pushes turns into BackgroundTaskManager subscriber queues for SSE streaming.

---

## 7. Evaluation System

### Five Independent Judges

Each judge is a separate LLM call with a specialized rubric.

| Judge | Range | What It Measures |
|-------|-------|-----------------|
| Goal Completion | 0–3 | Did the borrower commit to paying? |
| Conversational Quality | 1–5 | Repetition, acknowledgment, specificity, tone, hallucinations |
| Compliance | 0 or 1 | Any legal/ethical violations? Single violation = fail |
| Response Consistency | 0 or 1 | Does the agent contradict itself? |
| Sentiment Shift | -1 to +1 | Did the borrower's sentiment improve? |

### Score Aggregation

```python
SCORING_WEIGHTS = {
    "goal_completion": 0.35,
    "conversational_quality": 0.15,
    "compliance": 0.30,
    "response_consistency": 0.10,
    "sentiment_shift": 0.10,
}

# Normalize all to 0-1 → weighted sum → scale to 0-5
# Per-persona: median of N conversation scores
# Aggregate: mean of per-persona scores
```

---

## 8. Failure Analysis

`evolution/failure_analyzer.py` bridges evaluation and mutation. Raw scores tell you "what happened." Failure analysis tells you "why" and "what to change."

Output: Top 3 `FailurePattern` objects, each with description, target section, example turns, and suggested direction.

The analyzer is also informed by **cross-run accumulated tactics** from the playbook. Known successful tactics are appended to the analysis prompt so the analyzer can detect when failures violate proven approaches — connecting current problems to past solutions.

### Why Separate Analysis from Mutation

The analyzer diagnoses. The mutator prescribes. Combining them leads to sloppy mutations and loss of explainability.

---

## 9. Mutation Strategy

### Targeted Single-Section Rewrite

**Core principle**: Mutate one thing at a time. If you change two sections and the score goes up, you don't know which change helped.

2 candidates per mutation — run the mutation prompt twice (temperature > 0) for basic exploration.

### Playbook-Informed Mutation

The mutation prompt is enriched with context from the strategy playbook:
- **Proven tactics** for the target section — "these worked before, incorporate them"
- **Failed approaches** for the target section — "these were tried and failed, avoid them"

This is not a new LLM call — it's just additional context injected into the existing mutation prompt. The mutator gets both positive examples (what to do) and negative examples (what not to repeat), making each mutation more informed than the last.

---

## 10. Selection & Promotion

### Regression-Aware Hill Climbing

```
Candidate must:
1. Improve aggregate score over parent
2. Not regress any persona by > 0.5 points

If no candidate qualifies → parent stays champion, both candidates archived
```

This ensures **monotonic improvement across all personas**, not just the aggregate.

---

## 11. Evolution Loop Orchestration

`evolution/loop.py`:

```
INIT:
  Load base prompt → create v0 → simulate → evaluate
  → extract tactics from high-scoring v0 conversations → set champion

LOOP (max_generations):
  1. ANALYZE     — failure patterns from champion's conversations (with cross-run tactic context)
  2. TARGET      — highest-impact section (force different if stuck)
  3. MUTATE      — 2 candidate rewrites (with proven tactics + failed approaches from playbook)
  4. SIMULATE    — N conversations per persona per candidate (with persona-specific tactics in prompt)
  5. EVALUATE    — 5 judges per conversation
  6. EXTRACT     — winning tactics from high-scoring candidate conversations → save to playbook
  7. SELECT      — best non-regressing candidate
  8. RECORD      — failed candidates as FailedApproach → save to playbook
  9. TERMINATE?  — score ≥ threshold, or plateau, or budget hit
  10. DIVERSIFY  — on plateau: target untouched section

POST-LOOP:
  Champion = highest-scoring promoted version
  Playbook = accumulated tactics + failures from all generations
```

### Resume Support

The loop saves run metadata after every generation. Incomplete runs can be resumed — it detects incomplete state, rebuilds from MongoDB, and skips completed work.

---

## 12. Strategy Playbook (Persistent Knowledge)

### Motivation

Prompt rewriting alone is the shallowest form of self-modification. Each mutation starts from scratch — if the mutator tried something in generation 2 that failed, it might try the exact same thing in generation 4. If a conversation scored 4.5 because the agent used a specific de-escalation tactic, that insight dies with the conversation. The system rewrites *instructions* but never accumulates *knowledge*.

The strategy playbook adds persistent memory: **what worked** (reusable tactics) and **what failed** (anti-patterns). Both accumulate across generations and across runs in MongoDB, making the system genuinely learn from experience.

### Tactic Extraction (`evolution/tactic_extractor.py`)

After every evaluation, conversations scoring ≥ 3.5 (`TACTIC_SCORE_THRESHOLD`) are analyzed by an LLM call that extracts 1-3 specific, reusable tactics. Each tactic is:
- Tied to a **persona type** (angry, evasive, etc.) and a **prompt section**
- Deduplicated against existing tactics for that persona (LLM sees existing tactics and returns empty array if no new ones)
- Saved to `strategy_tactics` collection with the source conversation's score as `score_impact`

### Failure Recording

After selection, every non-promoted candidate is recorded as a `FailedApproach`:
- What was tried (the candidate's `rationale`)
- Why it failed (`no_improvement` or `regression`)
- Score delta and per-persona regressions

This is pure bookkeeping — no LLM call needed.

### Injection Points

The playbook feeds into the evolution loop at 4 points — all by enriching existing prompts, not by adding new LLM calls:

| Where | What Gets Injected | How |
|-------|-------------------|-----|
| **Simulation** (`persona_runner.py`) | Top 5 tactics for each persona type | `build_dynamic_prompt()` appends `## LEARNED TACTICS` section |
| **Failure Analysis** (`failure_analyzer.py`) | Top 10 tactics across all personas | Appended to the analysis prompt as "known successful tactics" |
| **Mutation** (`mutator.py`) | Top 5 tactics + top 5 failures for the target section | Injected as "PROVEN TACTICS" and "FAILED APPROACHES" blocks |
| **Voice Pipeline** (`pipeline.py`) | Top 5 tactics across all personas | Appended to the voice prompt |

### Cross-Run Learning

Tactics and failures persist in MongoDB. Run 2 automatically benefits from run 1's extracted knowledge. No manual intervention, no configuration — the playbook grows monotonically.

### Settings

```python
TACTIC_SCORE_THRESHOLD = 3.5    # Minimum weighted_total to extract tactics from a conversation
MAX_TACTICS_PER_PROMPT = 5      # Max tactics injected into a single prompt
```

---

## 13. Pipecat Voice Pipeline

### Architecture

```
Browser (React VoiceAgent page) ←── WebRTC ──→ SmallWebRTCTransport
       ↓
  [STT: Deepgram] ──── speech → text
       ↓
  [LLM: OpenAILLMService] ──── text → text (evolved prompt in context)
       ↓
  [TTS: Cartesia] ──── text → speech
       ↓
  SmallWebRTCTransport ←── WebRTC ──→ Browser
```

### Pipeline Assembly

`voice/pipeline.py` uses Pipecat's built-in services. The evolved prompt is injected as the system message in `OpenAILLMContext`, enriched with top tactics from the playbook (across all personas, since the voice agent doesn't know the caller's persona type in advance).

### Conversation Logging

`ConversationLoggerProcessor` captures turns from the voice pipeline and saves them to MongoDB with `source: "voice_live"`.

### Voice Context Override

The voice pipeline loads a voice-specific overlay from `prompts/voice_overlay.yaml` and appends it to the base prompt via `build_voice_prompt()` in `core/prompt_builder.py`. This overlay instructs the agent that it's a live call, doesn't know the borrower's name (must ask), and should never say `[borrower name]` literally. The base prompt stays intact for text simulation/evolution.

### Call Termination

The voice pipeline uses `[END_CALL:reason]` text markers for call termination — the same pattern as the simulation engine's `[END:reason]` signals. When the LLM includes `[END_CALL:goodbye]` (or `no_response`, `stop_calling`) in its output, `EndCallMarkerProcessor` strips the marker before TTS, disables idle timeout, and schedules an `EndFrame` after a 3-second grace period so the final audio plays through. This replaces the previous function-calling approach which was unreliable (LLM would narrate the tool call as speech).

### Silence / Idle Detection

The pipeline uses `LLMUserAggregatorParams(user_idle_timeout=7.0)` to detect when the borrower goes silent after the agent speaks. After 7 seconds of silence, a system message nudges the agent to check in. The idle counter resets to 0 whenever the user speaks (via `on_user_turn_started` handler), preventing premature escalation. After 3 consecutive idle events with no user speech, the agent wraps up with `[END_CALL:no_response]`.

### Future: Tool Calling for Borrower Lookup

Currently the agent has no access to borrower-specific data during live calls. A planned enhancement is to register OpenAI function-calling tools in the pipeline:

- **`lookup_borrower(name: str)`** — After the borrower identifies themselves, the agent calls this tool to retrieve loan details (account number, outstanding amount, overdue EMIs, due dates) from MongoDB. This makes conversations data-driven rather than generic.
- **`record_commitment(amount, date, mode)`** — Lets the agent log payment commitments in real-time during the call, rather than relying solely on post-call transcript analysis.

This would use `OpenAILLMService`'s native function-calling support with pipecat's `FunctionCallResultFrame` flow. The tools would be registered on the `OpenAILLMContext` and backed by service functions that query MongoDB.

### Subprocess Architecture

The voice pipeline runs as a separate subprocess on port 8001 (own event loop, clean start/stop). The main API proxies WebRTC SDP offers to the subprocess via `POST /api/voice/offer`. Health polling ensures the subprocess is ready before accepting calls.

---

## 14. FastAPI Backend

### App Factory Pattern

`api/main.py`: lifespan context manager initializes `BackgroundTaskManager` and seeds v0 on startup.

### API Routes

```
GET    /api/versions                → list all (summary)
GET    /api/versions/{id}           → full version detail
GET    /api/versions/champion       → current champion

GET    /api/conversations           → filtered (query: version_id, persona, source, outcome)
GET    /api/conversations/{id}      → full transcript + eval

GET    /api/evolution/runs          → list all runs
GET    /api/evolution/runs/{id}     → run detail with generation log
POST   /api/evolution/runs          → start new run (returns task_id)
DELETE /api/evolution/runs/{id}     → cancel running evolution
GET    /api/evolution/runs/{id}/stream → SSE: progress events

POST   /api/simulation              → start simulation (returns task_id)
GET    /api/simulation/{id}/stream  → SSE: live transcript turns

POST   /api/evaluation              → evaluate a conversation (sync)

GET    /api/voice/status            → is pipecat running?
POST   /api/voice/start             → start pipecat subprocess (blocks until ready)
POST   /api/voice/stop              → stop pipecat
POST   /api/voice/offer             → proxy WebRTC SDP to pipecat subprocess

GET    /api/playbook/tactics         → all tactics (newest first)
GET    /api/playbook/tactics/{persona} → tactics for a persona type
GET    /api/playbook/failures        → all failed approaches
GET    /api/playbook/stats           → summary: totals by persona/section

GET    /api/config                  → all non-secret settings
```

### Key Patterns

- **Services are stateless functions**, not classes — take explicit dependencies, return domain models
- **BackgroundTaskManager** holds per-task subscriber queues; `on_progress`/`on_turn` callbacks push into queues; SSE endpoints read from queues
- **Guard**: max 1 concurrent evolution task
- **Voice subprocess readiness**: `POST /start` polls `/health` on the subprocess until it responds (pipecat import takes ~15s)

---

## 15. React Frontend

### Stack

Vite + React + TypeScript + Tailwind CSS + Recharts. Light professional theme (white bg, subtle borders).

### 6 Pages

| Page | What It Does |
|------|-------------|
| **Personas** | 5 persona cards, simulate → live SSE transcript → eval scores |
| **Evolution** | Config form → start → SSE progress log → score chart (Recharts) |
| **Conversations** | 4 filter dropdowns, expandable table with transcripts + eval |
| **Archive** | Version list, prompt diffs from parent, per-persona score breakdowns |
| **Voice Agent** | Version selector, start/stop server, native WebRTC call (no iframe), history |
| **Playbook** | Accumulated tactics + failures across all runs, stats by persona/section |

### Key Patterns

- **State**: React hooks + fetch (no Redux)
- **Real-time**: SSE via custom `useSSE` hook wrapping `EventSource`
- **WebRTC**: Native in React — `getUserMedia`, `RTCPeerConnection`, SDP exchange via `/api/voice/offer`
- **Dev proxy**: Vite proxies `/api` to localhost:8000

---

## 16. Configuration & Environment

### .env

```bash
LLM_PROVIDER=openai                    # "openai" | "anthropic" | "google"
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=...
DEEPGRAM_API_KEY=...                   # STT
CARTESIA_API_KEY=...                   # TTS
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=darwin_godel
```

### config/settings.py

```python
MAX_GENERATIONS = 5
SCORE_THRESHOLD = 4.0
CONVERSATIONS_PER_PERSONA = 2
MAX_TURNS_PER_CONVERSATION = 20
MAX_PERSONA_REGRESSION = 0.5

SCORING_WEIGHTS = {
    "goal_completion": 0.35,
    "conversational_quality": 0.15,
    "compliance": 0.30,
    "response_consistency": 0.10,
    "sentiment_shift": 0.10,
}

# Playbook
TACTIC_SCORE_THRESHOLD = 3.5       # Min score to extract tactics from a conversation
MAX_TACTICS_PER_PROMPT = 5         # Max tactics injected into a single prompt
```

### MongoDB Collections

```
Database: darwin_godel
1. agent_versions     — one doc per version, indexed by id
2. conversations      — one doc per conversation, indexed by agent_version_id
3. evolution_runs     — one doc per evolution loop execution
4. strategy_tactics   — append-only, accumulates winning tactics across runs
5. failed_approaches  — append-only, accumulates failed mutation attempts across runs
```

---

## 17. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Sectioned prompts over monolithic | Targeted mutation, controlled experiments, readable diffs |
| 2 | Hill-climbing with 2 candidates | Basic exploration at ~2× cost, not N× for population-based |
| 3 | Regression detection per persona | Prevents oscillation — improving one persona while breaking another |
| 4 | Separate failure analysis from mutation | Diagnosis and prescription are different skills |
| 5 | Multiple conversations per persona (median) | LLM conversations are stochastic. Median reduces outlier impact |
| 6 | Immutable compliance section | Safety rail. Prevents optimizer from discovering "threatening works" |
| 7 | Per-turn annotations | Surgical targets for failure analyzer, not just holistic scores |
| 8 | Persistent playbook over stateless mutation | Prompt rewriting alone has no memory — the mutator repeats mistakes and loses winning tactics across runs. The playbook adds declarative + procedural memory |
| 9 | Tactic extraction from high-scoring convos | Knowledge should be extracted from success, not just inferred from failure. A conversation that scored 4.5 contains reusable tactics that should persist |
| 10 | Failed approach recording | Negative knowledge is as valuable as positive — prevents the mutator from trying the same thing twice |
| 11 | Per-persona tactic injection | Different personas need different tactics. A de-escalation tactic for angry borrowers would be counterproductive with cooperative ones |
| 12 | Text simulation first, voice last | Evolution loop is 95% of the work; voice is presentation layer |
| 13 | React + FastAPI over Streamlit | Proper API layer, SSE streaming, embeddable WebRTC, production-ready |
| 14 | Voice as subprocess | Own event loop, clean start/stop, no conflict with API server's asyncio |
| 15 | SSE over WebSocket | Unidirectional streaming is all we need; simpler than WebSocket |
| 16 | MongoDB over JSON files | Better querying + append-only playbook collections that accumulate across runs |
| 17 | Multi-provider LLM support | Switch between OpenAI, Anthropic, Google via env var |

---

*Last updated: March 2026*
