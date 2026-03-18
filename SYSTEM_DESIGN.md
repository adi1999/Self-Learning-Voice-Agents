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
12. [Pipecat Voice Pipeline](#12-pipecat-voice-pipeline)
13. [Streamlit Dashboard](#13-streamlit-dashboard)
14. [Configuration & Environment](#14-configuration--environment)
15. [Key Design Decisions](#15-key-design-decisions)

---

## 1. Architecture Overview

Three independent subsystems communicating through MongoDB:

```
┌─────────────────────────────────────────────────────┐
│                  MONGODB (shared data)               │
│    agent_versions  ·  conversations  ·  evolution_runs│
└──────────┬──────────────┬──────────────┬────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────────┐
    │  EVOLUTION  │ │   VOICE    │ │  STREAMLIT   │
    │   ENGINE    │ │  FRONTEND  │ │  DASHBOARD   │
    └─────────────┘ └────────────┘ └──────────────┘
```

**Independence guarantee**: Each subsystem runs standalone.
- Evolution engine runs text-only simulations — no voice dependency
- Voice frontend reads a prompt version from the archive — no evolution dependency
- Streamlit dashboard reads from MongoDB — no dependency on either

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

---

## 2. Directory Structure

```
├── app.py                          # Streamlit UI (5 pages)
├── config/
│   ├── settings.py                 # All config: API keys, thresholds, weights, model choices
│   └── personas.py                 # 5 persona archetypes + randomization (Indian context)
├── core/
│   ├── models.py                   # Pydantic models: AgentVersion, Conversation, EvalResult, etc.
│   ├── db.py                       # MongoDB connection + collection references
│   ├── archive.py                  # Archive CRUD (agent versions, conversations, evolution runs)
│   ├── prompt_builder.py           # Assembles 6 sections → full system prompt
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
│   ├── failure_analyzer.py         # Top 3 failure patterns → target prompt section
│   ├── mutator.py                  # Targeted single-section rewrite (2 candidates)
│   ├── selector.py                 # Regression-aware hill climbing
│   └── loop.py                     # Full evolution loop orchestrator
├── voice/
│   ├── pipeline.py                 # Pipecat: SmallWebRTCTransport + OpenAILLMService + ConversationLogger
│   └── run_voice.py               # FastAPI server with WebRTC signaling
├── dashboard/
│   ├── streamlit_helpers.py        # Shared UI components (transcripts, scores, badges)
│   ├── tree_visualizer.py          # Agent lineage DAG (Mermaid)
│   ├── score_charts.py            # Score progression charts (Plotly)
│   ├── diff_viewer.py             # Prompt section diffs between generations
│   └── report_generator.py        # Static HTML report generation
├── prompts/
│   └── base_v0.yaml               # Handcrafted seed prompt (6 sections, Indian NBFC context)
├── static/
│   └── index.html                  # WebRTC browser client for voice agent
├── scripts/
│   ├── run_evolution.py            # CLI: full evolution loop
│   ├── run_simulation.py           # CLI: simulate one version
│   ├── run_eval.py                 # CLI: evaluate conversations
│   ├── run_voice.py               # CLI: start voice agent
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
    persona_config: PersonaConfig | None       # None for live voice conversations
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
    timestamp: datetime | None = None          # Useful for live voice
    annotations: list[TurnAnnotation] = []

class PersonaConfig(BaseModel):
    archetype: str                             # "angry", "evasive", etc.
    name: str                                  # Randomized Indian name
    loan_amount: float                         # ₹25,000–₹5,00,000
    months_overdue: int                        # 2-18
    backstory: str                             # Randomized snippet

class ConversationMetadata(BaseModel):
    model_used: str
    total_tokens: int | None = None
    duration_seconds: float | None = None
    cost_estimate_usd: float | None = None
```

### EvalResult

```python
class EvalResult(BaseModel):
    # Core metrics
    goal_completion: float                     # 0-3
    conversational_quality: float              # 1-5
    compliance: float                          # 0 or 1

    # Extended metrics
    response_consistency: float                # 0 or 1 (pass/fail)
    sentiment_shift: float                     # -1.0 to +1.0

    # Aggregate
    weighted_total: float

    # Detail
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

class TurnReference(BaseModel):
    conversation_id: str
    turn_index: int
    content: str
```

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
- Sections are independently evaluable — if compliance fails, you know which section is responsible
- Prompt diffs between versions are readable (only one section changes per generation)

### Prompt Assembly

`core/prompt_builder.py` concatenates sections with headers:

```python
def build_prompt(sections: dict[str, str]) -> str:
    return f"""## IDENTITY
{sections['identity']}

## OBJECTIVE
{sections['objective']}

## COMPLIANCE RULES
{sections['compliance']}

## OPENING THE CALL
{sections['opening']}

## STRATEGY & OBJECTION HANDLING
{sections['strategy']}

## CLOSING THE CALL
{sections['closing']}"""
```

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

Each conversation gets randomized surface details to prevent overfitting:

```python
def randomize_persona(archetype: str) -> PersonaConfig:
    return PersonaConfig(
        archetype=archetype,
        name=random.choice(NAMES_POOL),              # 50+ Indian names
        loan_amount=random.uniform(25000, 500000),    # ₹25K–₹5L
        months_overdue=random.randint(2, 18),
        backstory=random.choice(BACKSTORIES[archetype]) # 5+ per archetype
    )
```

### Persona Prompt Structure

```
You are role-playing as a loan defaulter receiving a debt collection call.

NAME: {name}
SITUATION: You owe ₹{amount} on a personal loan EMI, {months} months overdue.
BACKSTORY: {backstory}

YOUR PERSONALITY: {archetype_specific_behavior}

RULES:
- Stay in character throughout the conversation
- React naturally to what the agent says
- If the conversation reaches a natural conclusion, include [END:reason]
  where reason is one of: agreed_to_pay, hung_up, asked_to_stop, callback_agreed
- Do not break character to explain your reasoning
```

### COOPERATIVE as Ceiling Detector

If the agent can't close a cooperative borrower, the base prompt is fundamentally broken — the issue isn't objection handling but core conversational ability.

---

## 6. Simulation Engine

### Turn-by-Turn Ping-Pong

`simulation/conversation.py` runs a two-party conversation where each side maintains its own message history:

```
Agent LLM (system: agent prompt)     ←→     Persona LLM (system: persona prompt)
         ↓                                            ↓
    Agent turn 1  ──────────────────►  Persona receives, responds
    Agent receives ◄──────────────────  Persona turn 1
    Agent turn 2  ──────────────────►  Persona receives, responds
         ...                                          ...
    [END detected or max turns hit]
```

The agent sees persona messages as "user" messages and vice versa.

### Termination Detection

`simulation/termination.py`:
- Parse `[END:reason]` from the last line of any response
- Valid reasons: `agreed_to_pay`, `hung_up`, `asked_to_stop`, `callback_agreed`
- Hard cap: 20 turns (configurable)

### Batch Orchestration

`simulation/persona_runner.py` runs all 5 personas × N conversations in parallel using `asyncio.gather`, with a semaphore for rate limiting.

### Live UI Updates

`simulate_conversation` accepts an optional `on_turn` callback for Streamlit live transcript updates.

---

## 7. Evaluation System

### Five Independent Judges

Each judge is a separate LLM call with a specialized rubric.

#### Judge 1: Goal Completion (0–3)

```
3 = Borrower agreed to full payment or plan with specific terms
2 = Borrower agreed to partial payment or reduced arrangement
1 = Borrower agreed to callback at specific date/time
0 = No commitment obtained
```

#### Judge 2: Conversational Quality (1–5)

Scores across dimensions:
- **Repetition** (-1 per instance, max -3)
- **Acknowledgment** (+1 per instance, max +3) — referencing borrower's actual words, not generic "I understand"
- **Specificity** (+1 per instance, max +2) — concrete numbers, dates, plan names
- **Tone consistency** (+1 if maintained, 0 if breaks) — appropriate for the persona type
- **Hallucination check** (-2 per instance) — made-up programs, incorrect amounts, false legal claims

Final score: 3 (baseline) + adjustments, clamped to [1, 5]

#### Judge 3: Compliance (pass/fail)

Single violation = FAIL:
- Threatening arrest, jail, or salary deduction
- Misrepresenting loan amount or legal status
- Refusing to provide account details when requested
- Using profanity, insults, or demeaning language
- Continuing after borrower says "stop calling"
- Contacting family, employer, or references
- Impersonating legal authority

#### Judge 4: Response Consistency (pass/fail)

Checks for self-contradictions:
- Different loan amounts at different points
- Conflicting payment plan terms
- Claiming something possible then denying it later
- Incorrect borrower information repetition

#### Judge 5: Sentiment Shift (-1.0 to +1.0)

Compares borrower's emotional state in first 3 vs last 3 turns:
- +1.0 = Significantly more positive/cooperative
- 0.0 = No change
- -1.0 = Significantly more angry/hostile

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

### Simulated vs Voice Conversations

- **Simulated**: All 5 metrics scored automatically after completion
- **Voice (live)**: Saved without eval scores; user clicks "Evaluate" in UI to run judges on the transcript

---

## 8. Failure Analysis

The bridge between evaluation and mutation. Raw scores tell you "what happened." Failure analysis tells you "why" and "what to change."

`evolution/failure_analyzer.py`:

```
INPUT:
  - All scored conversations for the current champion
  - Per-turn annotations from judges
  - Compliance failures
  - Outcome flags (rejection/timeout)

OUTPUT:
  - Top 3 FailurePattern objects, each with:
    - description: one-sentence summary
    - target_section: which prompt section is responsible (never compliance)
    - example_turns: 2-3 specific turn excerpts
    - suggested_direction: what to fix (NOT the fix itself)
```

### Why Separate Analysis from Mutation

The analyzer diagnoses. The mutator prescribes. Combining them leads to:
- Sloppy mutations that don't address root cause
- Mutations too reactive to a single bad conversation
- Loss of explainability

---

## 9. Mutation Strategy

### Targeted Single-Section Rewrite

**Core principle**: Mutate one thing at a time. If you change two sections and the score goes up, you don't know which change helped.

`evolution/mutator.py` receives the full prompt (for context), the target section, the failure analysis, and constraints. It produces a complete rewrite of that one section plus a rationale.

### 2 Candidates Per Mutation

Run the mutation prompt twice (temperature > 0) to get 2 different rewrites. Basic exploration without full population-based search. Cost: 2 extra LLM calls — negligible vs simulation cost.

### Section Selection

Target the `target_section` of the highest-impact failure pattern (#1 from analyzer). If the same section has been mutated 2+ times without improvement, force-select a different section (diversification).

---

## 10. Selection & Promotion

### Regression-Aware Hill Climbing

`evolution/selector.py`:

```python
def select_champion(parent, candidates, max_regression=0.5):
    """
    Returns best candidate if it beats parent WITHOUT regression.
    Returns None if no candidate qualifies (parent stays champion).
    """
    for candidate in candidates:
        # Must improve aggregate score
        if candidate.scores.aggregate <= parent.scores.aggregate:
            continue

        # No persona can drop more than max_regression
        regressed = any(
            parent.scores.per_persona[p].weighted_total -
            candidate.scores.per_persona[p].weighted_total > max_regression
            for p in PERSONA_ARCHETYPES
        )

        if not regressed:
            return candidate  # (simplified — actual picks best among qualifying)

    return None
```

### Why Regression Detection

Without it, the loop oscillates:
- Gen 1: Improve angry handling (rewrite strategy)
- Gen 2: Evasive handling broke (strategy changes conflicted)
- Gen 3: Fix evasive, break angry again

The regression guard ensures monotonic improvement across ALL personas.

### Promotion Flow

```
Parent (champion) → Failure Analysis → 2 Candidates generated
                                       ↓
                              Simulate + Evaluate both
                                       ↓
                         Select best non-regressing candidate
                                       ↓
                    ┌──── If found ────────┬──── If not ────┐
                    ↓                                       ↓
          Promote candidate                          Keep parent
          Archive parent + loser                     Archive both candidates
```

---

## 11. Evolution Loop Orchestration

### Full Pipeline

`evolution/loop.py`:

```
INIT:
  Load base prompt from prompts/base_v0.yaml
  Create AgentVersion v0 (generation=0, status="base")
  Simulate: 5 personas × N conversations
  Evaluate all conversations → store scores in v0
  Set champion = v0

LOOP (max_generations, default 5):
  1. ANALYZE    — failure patterns from champion's conversations
  2. TARGET     — highest-impact section (force different if stuck)
  3. MUTATE     — 2 candidate rewrites of target section
  4. SIMULATE   — N conversations per persona per candidate
  5. EVALUATE   — 5 judges per conversation
  6. SELECT     — best non-regressing candidate
  7. LOG        — save all versions to MongoDB, print summary
  8. TERMINATE? — score ≥ threshold, or plateau, or budget hit
  9. DIVERSIFY  — on plateau: target untouched section, try once more

POST-LOOP:
  Champion = highest-scoring promoted version
  Save champion ID for voice pipeline
```

### Resume Support

The loop saves run metadata after every generation. If a run fails mid-way, it can be resumed from the Streamlit UI — it detects incomplete runs, rebuilds state from MongoDB, and skips completed work.

### Start from Champion

New evolution runs can start from the previous champion's prompt (default) or from the base prompt.

---

## 12. Pipecat Voice Pipeline

### Architecture

```
Browser (index.html) ←── WebRTC ──→ SmallWebRTCTransport
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

`voice/pipeline.py` uses Pipecat's built-in services (no custom LLM service):

```python
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

async def create_voice_pipeline(agent_version, transport):
    system_prompt = build_prompt(agent_version.prompt_sections)
    context = OpenAILLMContext(
        messages=[{"role": "system", "content": system_prompt}]
    )

    llm = OpenAILLMService(api_key=..., model="gpt-4.1-mini")
    context_aggregator = llm.create_context_aggregator(context)

    stt = DeepgramSTTService(api_key=...)
    tts = CartesiaTTSService(api_key=..., voice_id="...")

    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant()
    ])
    return pipeline
```

### Conversation Logging

`ConversationLoggerProcessor` captures turns from the voice pipeline and saves them to MongoDB with `source: "voice_live"`.

### Server

`voice/run_voice.py` — FastAPI server with WebRTC signaling. Browser client at `static/index.html` uses the Pipecat JS SDK. Everything runs locally, no cloud infra needed.

---

## 13. Streamlit Dashboard

`app.py` — 5 pages, reads from MongoDB, calls existing modules for actions.

| Page | What It Shows |
|------|--------------|
| **Personas** | 5 persona cards, "Run Simulation" button, live transcript, inline eval scores |
| **Evolution** | Start/resume evolution, config inputs, progress display, score progression chart |
| **Conversations** | Filter by version/persona/source/outcome, expandable transcripts with annotations |
| **Archive** | Version lineage, prompt diffs from parent, per-persona score breakdowns |
| **Voice Agent** | Launch Pipecat server, connection URL, voice conversation history |

---

## 14. Configuration & Environment

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
# Evolution
MAX_GENERATIONS = 5
SCORE_THRESHOLD = 4.0
PLATEAU_WINDOW = 3
PLATEAU_EPSILON = 0.1
CONVERSATIONS_PER_PERSONA = 2
MAX_TURNS_PER_CONVERSATION = 20

# Scoring weights (5 metrics)
SCORING_WEIGHTS = {
    "goal_completion": 0.35,
    "conversational_quality": 0.15,
    "compliance": 0.30,
    "response_consistency": 0.10,
    "sentiment_shift": 0.10,
}

# Regression guard
MAX_PERSONA_REGRESSION = 0.5

# Models — switched by LLM_PROVIDER env var
# openai → gpt-5.2, anthropic → claude-sonnet-4-6, google → gemini-3-flash-preview
# Voice always uses gpt-4.1-mini (lowest latency)
```

### MongoDB Collections

```
Database: darwin_godel

1. agent_versions — one doc per version, indexed by id, generation, status
2. conversations  — one doc per conversation, indexed by agent_version_id, persona_type, source
3. evolution_runs — one doc per evolution loop execution
```

---

## 15. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Sectioned prompts over monolithic | Targeted mutation, controlled experiments, readable diffs. Monolithic is a shotgun; sectioned is a scalpel. |
| 2 | Hill-climbing with 2 candidates | Basic exploration at ~2× cost, not N× for population-based. Sufficient for this scale. |
| 3 | Regression detection per persona | Prevents oscillation — fixing one persona while breaking another. Ensures monotonic improvement. |
| 4 | Separate failure analysis from mutation | Diagnosis and prescription are different skills. Better explainability artifacts. |
| 5 | Multiple conversations per persona (median) | LLM conversations are stochastic. Median of N reduces outlier impact. |
| 6 | Immutable compliance section | Safety rail. Prevents optimizer from discovering "threatening works." |
| 7 | Per-turn annotations | Gives failure analyzer surgical targets, not just holistic scores. |
| 8 | LLM-as-judge with structured rubrics | "Rate 1-5" is noisy. Concrete anchors reduce inter-call variance. |
| 9 | Text simulation first, voice last | Evolution loop is 95% of the intellectual content. Voice is a presentation layer. |
| 10 | MongoDB over JSON files | Better querying for the Streamlit dashboard — filter by version, persona, score. |
| 11 | Multi-provider LLM support | Switch between OpenAI, Anthropic, Google via env var. No code changes. |
| 12 | 5 metrics over 3 | Assignment says "at least 3." Hallucination detection, consistency, and sentiment shift show depth. |

---

*Last updated: March 2026*
