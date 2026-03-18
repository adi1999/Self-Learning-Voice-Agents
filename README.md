# Self-Evolving Voice Agent

A platform that **automatically evolves** a debt collection voice agent's prompts through simulated conversations, automated evaluation, failure analysis, and targeted prompt mutation — without human intervention.

The system simulates conversations against 5 borrower personas, scores them across 5 metrics using LLM judges, identifies failure patterns, rewrites the weakest prompt section, and promotes improvements — all in a closed loop. The final evolved prompt powers a real-time voice agent via Pipecat.

---

## How It Works

```
                    ┌──────────────────────────────┐
                    │     1. SIMULATE (LLM ↔ LLM)  │
                    │  Agent vs 5 borrower personas │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     2. EVALUATE (5 judges)    │
                    │  Goal · Quality · Compliance  │
                    │  Consistency · Sentiment       │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     3. ANALYZE FAILURES       │
                    │  Top 3 patterns → which       │
                    │  prompt section to fix         │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     4. MUTATE (2 candidates)  │
                    │  Rewrite target section only   │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     5. SELECT (hill-climbing)  │
                    │  Promote if better + no        │
                    │  per-persona regression         │
                    └──────────────┬───────────────┘
                                   │
                         Loop until threshold
                         reached or plateau
```

### Evolution in Action

Starting from a handcrafted base prompt (v0), the system ran 5 generations and improved the aggregate score from **3.45 → 4.06**, hitting the success threshold. Key mutation: rewriting the `objective` section at Generation 3 produced a breakthrough after `strategy` mutations had plateaued.

---

## Architecture

Three independent subsystems communicating through MongoDB:

| Subsystem | What It Does | Runs Without |
|-----------|-------------|-------------|
| **Evolution Engine** | Simulate → Evaluate → Analyze → Mutate → Select | Voice, Dashboard |
| **Voice Frontend** | Pipecat pipeline: STT → LLM → TTS over WebRTC | Evolution |
| **Streamlit Dashboard** | Live UI for personas, evolution runs, conversations, archive | Everything (reads DB) |

```
config/          ← depends on nothing
core/            ← depends on config
simulation/      ← depends on core
evaluation/      ← depends on core
evolution/       ← depends on simulation, evaluation, core
voice/           ← depends on core (+ Pipecat)
dashboard/       ← depends on core
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

**Why compliance weight is 30%**: A compliant conversation that fails to close is better than an illegal conversation that succeeds.

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
- MongoDB (local instance)
- API keys: OpenAI or Anthropic or Google, plus Deepgram and Cartesia for voice

### Installation

```bash
git clone https://github.com/<your-username>/Self-Learning-Voice-Agents.git
cd Self-Learning-Voice-Agents

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

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

# Voice Services
DEEPGRAM_API_KEY=...          # STT
CARTESIA_API_KEY=...          # TTS

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=darwin_godel
```

---

## Usage

### Streamlit Dashboard (recommended)

```bash
streamlit run app.py
```

The dashboard provides 5 pages:

1. **Personas** — View persona cards, run individual simulations with live transcript updates
2. **Evolution** — Start/resume evolution runs, view score progression charts
3. **Conversations** — Filter and browse all conversation transcripts with evaluation breakdowns
4. **Archive** — View agent version lineage, prompt diffs, per-persona scores
5. **Voice Agent** — Launch the Pipecat voice agent, browse voice conversation history

### CLI Scripts

```bash
# Run the full evolution loop
python scripts/run_evolution.py --max-generations 5 --threshold 4.0

# Simulate a single version against all personas
python scripts/run_simulation.py --version v0

# Re-evaluate existing conversation logs
python scripts/run_eval.py --version v0

# Start the voice agent with a specific prompt version
python scripts/run_voice.py --version <champion-id>

# Generate static HTML report
python scripts/generate_report.py

# Export MongoDB data to JSON (for GitHub submission)
python scripts/export_json.py
```

---

## Project Structure

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
└── data/                           # Exported JSON data (from export_json.py)
    ├── archive/
    ├── conversations/
    └── reports/
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Sectioned prompts over monolithic | Targeted mutation, controlled experiments, readable diffs |
| Hill-climbing with 2 candidates | Basic exploration at ~2× cost, not N× for population-based |
| Regression detection per persona | Prevents oscillation — improving one persona while regressing another |
| Separate failure analysis from mutation | Diagnosis and prescription are different skills; better explainability |
| 3 conversations per persona (median) | Reduces noise from LLM stochasticity |
| Immutable compliance section | Safety rail against the optimizer gaming the metric |
| Per-turn annotations | Surgical targets for the failure analyzer, not just holistic scores |
| Text simulation first, voice last | Evolution loop is 95% of the work; voice is a presentation layer |
| MongoDB over JSON files | Better querying for the Streamlit dashboard (filter by version, persona, score) |
| Multi-provider LLM support | Switch between OpenAI, Anthropic, Google via env var — no code changes |

---

## Language Support

The current implementation uses English in an Indian financial context (NBFC terminology, RBI compliance, EMI/UPI/NEFT references). The architecture is language-agnostic — adding Hindi/Hinglish support requires only:

1. Translating persona prompts in `config/personas.py`
2. Selecting appropriate TTS voices (e.g., ElevenLabs Multilingual V2)
3. Ensuring STT model supports the target language (Deepgram supports Hindi)
4. Updating evaluation judge prompts to evaluate in the target language

No architectural changes needed.

---

## Cost

| Scenario | Generations | Est. LLM Calls | Est. Cost |
|----------|-------------|-----------------|-----------|
| Quick test | 3 | ~2,100 | $2–5 |
| Standard run | 5 | ~3,500 | $3–10 |
| Deep run | 10 | ~7,000 | $5–15 |

Actual cost depends on conversation length and model choice.

---

## References

- [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) — ruthless simplicity pattern
- [Pipecat](https://github.com/pipecat-ai/pipecat) — open-source voice AI pipeline framework
