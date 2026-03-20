# Self-Evolving Voice Agent

A platform that **automatically evolves** a debt collection voice agent through simulated conversations, automated evaluation, failure analysis, targeted prompt mutation, and persistent knowledge accumulation — without human intervention.

The system simulates conversations against 5 borrower personas, scores them across 5 metrics using LLM judges, identifies failure patterns, rewrites the weakest prompt section, and promotes improvements — all in a closed loop. Beyond prompt rewriting, it extracts winning tactics from high-scoring conversations and records failed mutation approaches into a **strategy playbook** that persists across runs, so the system genuinely learns from experience rather than just rewords instructions. The final evolved prompt — enriched with accumulated knowledge — powers a real-time voice agent via Pipecat.

---

## How It Works

```
                    ┌──────────────────────────────┐
                    │     1. SIMULATE (LLM ↔ LLM)  │
                    │  Agent vs 5 borrower personas │
                    │  (with learned tactics injected│
                    │   per persona from playbook)   │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     2. EVALUATE (5 judges)    │
                    │  Goal · Quality · Compliance  │
                    │  Consistency · Sentiment       │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  3. EXTRACT TACTICS (playbook) │
                    │  High-scoring convos → reusable│
                    │  tactics saved to MongoDB      │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     4. ANALYZE FAILURES       │
                    │  Top 3 patterns → which       │
                    │  prompt section to fix         │
                    │  (informed by cross-run tactics)│
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     5. MUTATE (2 candidates)  │
                    │  Rewrite target section, with  │
                    │  proven tactics + failed        │
                    │  approaches from playbook       │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     6. SELECT (hill-climbing)  │
                    │  Promote if better + no        │
                    │  per-persona regression         │
                    │  Record failures to playbook   │
                    └──────────────┬───────────────┘
                                   │
                         Loop until threshold
                         reached or plateau
```

### How We Built This — Two Phases

We started with the simplest thing that could work: **prompt-level string rewriting**.

**Phase 1 — Prompt Evolution (hill-climbing):** The system simulates conversations, evaluates with 5 judges, analyzes failures, rewrites one prompt section at a time, and selects non-regressing candidates. This is a closed loop that optimizes *what the agent says* — the literal text of its system prompt. Starting from a handcrafted base prompt (v0), this loop ran 5 generations and improved the aggregate score from **3.45 → 4.06**, hitting the success threshold.

But prompt rewriting has a fundamental limitation: **it has no memory**. Each mutation starts from scratch. If the mutator tried something in generation 2 that failed, it might try the exact same thing in generation 4. If a conversation with an angry borrower scored 4.5 because the agent used a specific de-escalation tactic, that insight dies with the conversation — it never gets extracted or reused.

This is the shallowest form of self-modification. The system rewrites *instructions* but never accumulates *knowledge*.

**Phase 2 — Persistent Knowledge (playbook):** Inspired by how Hermes Agent (Nous Research) achieves genuine self-improvement through procedural memory (skills), declarative memory, and episodic recall, we added a **strategy playbook** — a persistent knowledge layer that accumulates across generations and across runs.

After each evaluation, the system now:
- **Extracts winning tactics** from high-scoring conversations (score >= 3.5) — concrete, reusable strategies tied to specific persona types and prompt sections
- **Records failed approaches** when candidates aren't promoted — what was tried, why it failed, score deltas

This accumulated knowledge feeds back into the loop at every stage:
- **Simulation**: Persona-specific tactics are injected into the live prompt, so the agent's behavior reflects everything it has ever learned, not just the latest prompt rewrite
- **Failure analysis**: Cross-run tactics inform pattern detection — the analyzer knows what has worked before
- **Mutation**: The mutator sees both proven tactics to incorporate and failed approaches to avoid, so it never repeats the same mistake twice

The key insight: Phase 1 optimizes *what the agent says*. Phase 2 optimizes *what the agent knows*. Together, they create a system that genuinely learns from experience rather than just rewords instructions.

---

## Architecture

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
    ↓
Pipecat Voice Pipeline (subprocess, port 8001)
    STT (Deepgram) → LLM (OpenAI) → TTS (Cartesia) → WebRTC
```

Three independent subsystems:

| Subsystem | What It Does | Runs Without |
|-----------|-------------|-------------|
| **Evolution Engine** | Simulate → Evaluate → Extract tactics → Analyze → Mutate → Select → Record failures | Voice, Dashboard |
| **Voice Pipeline** | Pipecat: STT → LLM → TTS over WebRTC | Evolution |
| **React + FastAPI Dashboard** | Full UI for all operations + Playbook viewer | Evolution, Voice (reads DB) |

```
config/          ← depends on nothing
core/            ← depends on config
simulation/      ← depends on core
evaluation/      ← depends on core
evolution/       ← depends on simulation, evaluation, core
voice/           ← depends on core (+ Pipecat)
api/             ← depends on everything (HTTP layer)
frontend/        ← depends on api (HTTP only)
scripts/         ← thin CLI wrappers
```

---

## Prompt Design

The agent prompt is split into **6 independently mutable sections**:

| Section | Purpose | Mutable? |
|---------|---------|----------|
| `identity` | Who the agent is (name, company, personality) | Yes |
| `objective` | Goals and acceptable outcomes hierarchy | Yes |
| `compliance` | Hard legal rules (RBI Fair Practices Code) | **No — immutable safety rail** |
| `opening` | How to start the call | Yes |
| `strategy` | Objection handling for each persona type | Yes |
| `closing` | Commitment-securing techniques | Yes |

**Why sectioned?** Each section maps to a distinct failure mode. Only one section is mutated per generation (Karpathy principle: change one variable at a time). This gives clean diffs, explainability, and controlled experiments.

**Why compliance is immutable?** Without this constraint, the optimizer could discover that "threatening borrowers increases goal completion." The immutable compliance section prevents gaming.

---

## 5 Borrower Personas

Simulated with Indian context — names, amounts in Rupees, EMI terminology, NBFC/RBI references.

| Persona | Behavior | Tests Agent's Ability To... |
|---------|----------|-----------------------------|
| **Angry** | Hostile, threatens RBI complaint, questions legitimacy | De-escalate, maintain composure |
| **Evasive** | Dodges questions, "salary hasn't come", keeps postponing | Create urgency, redirect |
| **Hardship** | Lost job, medical emergency, genuinely can't pay | Show empathy, offer alternatives |
| **Informed** | Cites RBI guidelines, SARFAESI Act, knows legal rights | Handle legal questions accurately |
| **Cooperative** | Willing to pay, asks about options | Close efficiently (ceiling detector) |

Each conversation gets randomized surface details (name, loan amount ₹25K–₹5L, months overdue, backstory) to prevent overfitting.

---

## 5 Evaluation Metrics

Each conversation is scored by 5 independent LLM judges:

| Metric | Range | Weight | What It Measures |
|--------|-------|--------|-----------------|
| Goal Completion | 0–3 | 35% | Did the borrower commit to paying? |
| Conversational Quality | 1–5 | 15% | Repetition, acknowledgment, specificity, tone, hallucinations |
| Compliance | 0 or 1 | 30% | Any legal/ethical violations? Single violation = fail |
| Response Consistency | 0 or 1 | 10% | Does the agent contradict itself? |
| Sentiment Shift | -1 to +1 | 10% | Did the borrower's sentiment improve? |

**Per-persona scores** use the median of N conversations (not mean) to reduce outlier impact from LLM stochasticity.

---

## Selection & Regression Detection

The selector uses **regression-aware hill climbing**:

- A candidate must improve the aggregate score over the parent
- **No persona can regress by more than 0.5 points** — prevents oscillation (fixing angry handling while breaking evasive)
- If no candidate qualifies, the parent stays champion and both candidates are archived

This ensures **monotonic improvement across all personas**, not just the aggregate.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for React frontend)
- MongoDB (local instance)
- API keys: OpenAI or Anthropic or Google, plus Deepgram and Cartesia for voice

### Installation

```bash
git clone https://github.com/<your-username>/Self-Learning-Voice-Agents.git
cd Self-Learning-Voice-Agents

# Python backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# React frontend
cd frontend
npm install
cd ..

# Copy and fill in API keys
cp .env.example .env
# Edit .env with your keys
```

### Environment Variables

```bash
# LLM Provider (pick one): "openai" | "anthropic" | "google"
LLM_PROVIDER=openai

# LLM API Key (whichever provider you chose)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=...

# Voice Services (only needed for voice agent)
DEEPGRAM_API_KEY=...          # STT
CARTESIA_API_KEY=...          # TTS

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=darwin_godel
```

---

## Usage

### Development (two terminals)

```bash
# Terminal 1: FastAPI backend
source .venv/bin/activate
python scripts/run_api.py

# Terminal 2: React frontend
cd frontend
npm run dev
```

Open http://localhost:3000

### Production (single port)

```bash
cd frontend && npm run build && cd ..
source .venv/bin/activate
python scripts/run_api.py
```

Open http://localhost:8000

### Dashboard Pages

1. **Personas** — 5 persona cards, run individual simulations with live SSE transcript updates, inline eval scores
2. **Evolution** — Configure and start evolution runs, real-time progress streaming, score progression charts
3. **Conversations** — Filter and browse all conversation transcripts with evaluation breakdowns
4. **Archive** — Agent version lineage, prompt diffs from parent, per-persona score tables
5. **Voice Agent** — Start/stop Pipecat voice server, native WebRTC call directly in browser, voice conversation history
6. **Playbook** — Accumulated strategy tactics and failed approaches across all evolution runs

### CLI Scripts

```bash
# Run the full evolution loop
python scripts/run_evolution.py --max-generations 5 --threshold 4.0

# Simulate a single version against all personas
python scripts/run_simulation.py --version v0

# Re-evaluate existing conversation logs
python scripts/run_eval.py --version v0

# Start the voice agent standalone (without React)
python scripts/run_voice.py --version <champion-id>

# Generate static HTML report
python scripts/generate_report.py

# Export MongoDB data to JSON
python scripts/export_json.py
```

---

## Project Structure

```
├── config/                         # Configuration (API keys, thresholds, personas)
├── core/                           # Shared domain: models, archive, prompt builder, LLM client
├── simulation/                     # Turn-by-turn conversation engine
├── evaluation/                     # 5 LLM judges + score aggregation
├── evolution/                      # Failure analysis, mutation, selection, loop orchestrator
├── voice/                          # Pipecat pipeline + WebRTC server
├── api/                            # FastAPI: routers, services, schemas, task manager
│   ├── routers/                    # REST endpoints (versions, conversations, evolution, etc.)
│   ├── services/                   # Stateless service functions bridging routers → core
│   └── schemas/                    # Pydantic request/response models
├── frontend/                       # React + Vite + TypeScript + Tailwind
│   └── src/
│       ├── pages/                  # 6 pages: Personas, Evolution, Conversations, Archive, Voice, Playbook
│       ├── components/             # Reusable UI components
│       ├── hooks/                  # useSSE hook
│       └── api/                    # Typed fetch client
├── dashboard/                      # HTML report generation (Jinja2 templates)
├── prompts/                        # Base prompt YAML
├── scripts/                        # CLI entry points
└── data/                           # Exported JSON data
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Sectioned prompts over monolithic | Targeted mutation, controlled experiments, readable diffs |
| Hill-climbing with 2 candidates | Basic exploration at ~2× cost, not N× for population-based |
| Regression detection per persona | Prevents oscillation — improving one persona while regressing another |
| Separate failure analysis from mutation | Diagnosis and prescription are different skills; better explainability |
| Multiple conversations per persona (median) | Reduces noise from LLM stochasticity |
| Immutable compliance section | Safety rail against the optimizer gaming the metric |
| Per-turn annotations | Surgical targets for the failure analyzer, not just holistic scores |
| Persistent playbook over stateless mutation | Prompt rewriting alone has no memory — the mutator repeats mistakes and loses winning tactics across runs |
| Tactic extraction from high-scoring convos | Knowledge should be extracted from success, not just inferred from failure patterns |
| Failed approach recording | Prevents the mutator from trying the same thing twice — negative knowledge is as valuable as positive |
| Per-persona tactic injection | Different personas need different tactics; a de-escalation tactic for angry borrowers hurts with cooperative ones |
| Text simulation first, voice last | Evolution loop is 95% of the work; voice is a presentation layer |
| React + FastAPI over Streamlit | Proper API layer, SSE streaming, native WebRTC, production-ready |
| Voice as subprocess | Own event loop, clean start/stop, no asyncio conflicts |
| MongoDB over JSON files | Better querying — filter by version, persona, score; append-only playbook collections accumulate across runs |
| Multi-provider LLM support | Switch between OpenAI, Anthropic, Google via env var — no code changes |

---

## Language Support

The current implementation uses English in an Indian financial context (NBFC terminology, RBI compliance, EMI/UPI/NEFT references). The architecture is language-agnostic — adding Hindi/Hinglish support requires only:

1. Translating persona prompts in `config/personas.py`
2. Selecting appropriate TTS voices
3. Ensuring STT model supports the target language
4. Updating evaluation judge prompts

No architectural changes needed.

---

## Cost

| Scenario | Generations | Est. LLM Calls | Est. Cost |
|----------|-------------|-----------------|-----------|
| Quick test | 3 | ~2,100 | $2–5 |
| Standard run | 5 | ~3,500 | $3–10 |
| Deep run | 10 | ~7,000 | $5–15 |

Actual cost depends on conversation length and model choice.

### Token Usage Note

Both the agent-to-agent simulation and the live voice pipeline use **stateless LLM APIs** (OpenAI, Anthropic, Google). This means the **full conversation history is resent with every turn** — there is no server-side session. In a 20-turn conversation, turn 20's API call includes turns 1–19 plus the system prompt as input tokens. This is the standard approach for all Chat Completions-style APIs and is how context is maintained. The tradeoff is higher input token cost in exchange for simplicity and reliability (no session state to manage or lose). Possible optimizations include sliding-window context (only send last N turns), periodic summarization of older turns, or leveraging provider-side prompt caching (OpenAI and Anthropic automatically cache repeated prefixes, reducing cost on the system prompt + early turns).

---

## Limitations & Roadmap

### Known Limitations

**LLM-as-judge circularity.** The system is LLMs all the way down — LLM personas, LLM agent, LLM judges, LLM failure analyzer, LLM mutator. There is no ground truth anchor. The optimizer might learn to satisfy judge preferences rather than actual collection effectiveness. A persona LLM saying "I'll pay" is not a real borrower paying.

**Sim-to-real gap.** Simulated personas follow their archetype instructions faithfully. Real humans interrupt, ramble, switch languages mid-sentence, go silent, lie inconsistently, or pick up the phone thinking it's someone else. The 5 archetypes also miss real-world types: confused elderly callers, non-native speakers, someone who already paid and is angry, or a family member who answered.

**No structured data capture.** The agent talks but captures nothing verifiable. There's no tool call to look up borrower details, no structured commitment record (amount + date + mode), no post-call extraction. Evaluation is purely holistic transcript reading — "vibes-based" rather than fact-based.

**No multi-call memory.** Real debt collection is multi-touch. "Mr. Sharma, when we spoke Tuesday you mentioned your salary comes on the 25th." The system treats every call as a cold start.

**No conversation efficiency signal.** A 20-turn conversation scoring 3.5 and a 6-turn conversation scoring 3.5 are treated identically. In production, shorter successful calls = more calls per hour = more revenue.

### Roadmap (by impact)

1. **Human-labeled calibration set** — 20 conversations scored by humans. Compare to LLM judges. If correlation is low, the judges are measuring the wrong thing. Everything else is pointless without this.
2. **Tool calls (lookup + record_commitment)** — Structured, verifiable output. Transforms "did the persona say yes" into "did the agent correctly capture commitment details." Objective ground truth within simulation.
3. **Rule-based compliance hard gate** — Regex/pattern matching for banned phrases and threats, running before the LLM compliance judge. Non-negotiable for financial services.
4. **Structured extraction → deterministic scoring** — Parse transcripts into structured records (identity verified, commitment amount/date, reason for default). Replace subjective LLM judges with deterministic scoring wherever possible. Reserve LLM judges only for genuinely subjective dimensions (tone, quality).
5. **More persona types** — Confused, already-paid-and-angry, family-member-answered. Cheap to add, catches real failure modes.
6. **Conversation efficiency metric** — Turns-to-resolution as a scoring factor.
7. **A/B testing framework** — Route calls between prompt versions, compare real outcomes.
8. **Multi-call memory** — Cross-session context for repeat borrowers.

---

## References

- [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) — ruthless simplicity pattern
- [Pipecat](https://github.com/pipecat-ai/pipecat) — open-source voice AI pipeline framework
