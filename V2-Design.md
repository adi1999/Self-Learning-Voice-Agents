# Darwin-Gödel Voice Agent — V2 Updates & Requirements

> **Context**: We have an existing implementation based on the original `SYSTEM_DESIGN.md`. This document specifies the changes, additions, and corrections needed. Claude Code should read this alongside the existing codebase and apply these updates.

---

## Summary of Changes

| Area | What Changed | Why |
|---|---|---|
| Storage | JSON files → MongoDB | Better querying for UI, filtering by version/persona/score |
| UI | None → Streamlit app | Assignment asks for "2-3 min demo of the platform" — need visual layer |
| Metrics | 3 metrics → 5 metrics | Assignment says "at least 3"; adding hallucination, tone, consistency, sentiment shows depth |
| Conversation Model | Missing `source` field | Need to distinguish simulated vs live voice conversations |
| Voice Pipeline | Custom LLM service → OpenAILLMService | Pipecat API correction — use built-in services, not custom |
| Voice Transport | LocalTransport → SmallWebRTCTransport | Pipecat's recommended local approach, easier to demo/record |
| UI Modes | None → Two modes (Talk to Agent + Simulate) | Need both live voice and triggered simulation from UI |
| Persona Triggering | Only batch via evolution loop → Also individual from UI | Debugging, demo-ability, manual testing |

---

## 1. MongoDB Integration

### Database Structure

```
Database: darwin_godel

Collections:

1. agent_versions
   - One document per agent version
   - Indexed by: id, generation, status
   - Contains: prompt_sections, scores, rationale, failure_patterns, lineage

2. conversations
   - One document per conversation
   - Indexed by: agent_version_id, persona_type, source, outcome
   - Contains: full turn-by-turn transcript, eval results, annotations, metadata

3. evolution_runs
   - One document per evolution loop execution
   - Contains: config used, generations completed, champion_id, termination_reason,
     start_time, end_time, cost_tracking
```

### Connection Setup

```python
# core/db.py (NEW FILE)

from pymongo import MongoClient
from config.settings import MONGO_URI, MONGO_DB_NAME

client = MongoClient(MONGO_URI)  # default: "mongodb://localhost:27017"
db = client[MONGO_DB_NAME]       # default: "darwin_godel"

agent_versions_collection = db["agent_versions"]
conversations_collection = db["conversations"]
evolution_runs_collection = db["evolution_runs"]
```

### Changes to core/archive.py

Replace all JSON file read/write with MongoDB operations:

```python
# BEFORE (JSON files):
def save_version(version: AgentVersion):
    with open(f"data/archive/{version.id}.json", "w") as f:
        json.dump(version.dict(), f)

# AFTER (MongoDB):
def save_version(version: AgentVersion):
    doc = version.dict()
    agent_versions_collection.update_one(
        {"id": version.id},
        {"$set": doc},
        upsert=True
    )

def get_version(version_id: str) -> AgentVersion:
    doc = agent_versions_collection.find_one({"id": version_id})
    return AgentVersion(**doc)

def get_all_versions() -> list[AgentVersion]:
    return [AgentVersion(**doc) for doc in agent_versions_collection.find().sort("generation", 1)]

def get_champion() -> AgentVersion:
    return AgentVersion(**agent_versions_collection.find_one({"status": "promoted"}, sort=[("generation", -1)]))

def get_versions_by_status(status: str) -> list[AgentVersion]:
    return [AgentVersion(**doc) for doc in agent_versions_collection.find({"status": status})]
```

Similar pattern for conversations:

```python
def save_conversation(conv: Conversation):
    conversations_collection.update_one(
        {"id": conv.id},
        {"$set": conv.dict()},
        upsert=True
    )

def get_conversations_for_version(version_id: str) -> list[Conversation]:
    return [Conversation(**doc) for doc in
            conversations_collection.find({"agent_version_id": version_id})]

def get_conversations_filtered(
    version_id: str = None,
    persona_type: str = None,
    source: str = None,
    outcome: str = None
) -> list[Conversation]:
    query = {}
    if version_id: query["agent_version_id"] = version_id
    if persona_type: query["persona_type"] = persona_type
    if source: query["source"] = source
    if outcome: query["outcome"] = outcome
    return [Conversation(**doc) for doc in conversations_collection.find(query)]
```

### JSON Export Script

Keep a `scripts/export_json.py` that dumps MongoDB collections to `data/` for the GitHub repo:

```python
# scripts/export_json.py
# Dumps all collections to data/ as JSON files for GitHub submission
# Run: python scripts/export_json.py

def export_all():
    versions = list(agent_versions_collection.find({}, {"_id": 0}))
    conversations = list(conversations_collection.find({}, {"_id": 0}))
    runs = list(evolution_runs_collection.find({}, {"_id": 0}))

    with open("data/archive/versions.json", "w") as f:
        json.dump(versions, f, indent=2, default=str)
    with open("data/conversations/all_conversations.json", "w") as f:
        json.dump(conversations, f, indent=2, default=str)
    with open("data/evolution_runs.json", "w") as f:
        json.dump(runs, f, indent=2, default=str)
```

### Config Addition

```python
# config/settings.py — add:
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "darwin_godel")
```

```bash
# .env.example — add:
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=darwin_godel
```

### New File

```
core/
├── db.py                 # NEW: MongoDB connection + collection references
```

---

## 2. Updated Conversation Model

### Changes to core/models.py

Add `source` field and enhanced metadata:

```python
class Conversation(BaseModel):
    id: str                                    # UUID or "{version}_{persona}_{run_number}"
    agent_version_id: str
    persona_type: str | None                   # None for live voice conversations
    persona_config: PersonaConfig | None       # None for live voice conversations
    source: Literal["simulation", "voice_live"]  # NEW: how this conversation was created
    turns: list[Turn]
    outcome: Literal["success", "rejection", "hallucination", "timeout", "ended_by_user"]
    duration_turns: int
    eval_result: EvalResult | None
    metadata: ConversationMetadata             # NEW

    created_at: datetime

class ConversationMetadata(BaseModel):         # NEW
    model_used: str                            # e.g., "gpt-4o-mini"
    total_tokens: int | None = None
    duration_seconds: float | None = None      # Wall clock time
    cost_estimate_usd: float | None = None

class Turn(BaseModel):
    index: int
    role: Literal["agent", "borrower"]
    content: str
    timestamp: datetime | None = None          # NEW: useful for live voice
    annotations: list[TurnAnnotation] = []     # CHANGED: list of TurnAnnotation, not str
```

---

## 3. Expanded Evaluation Metrics (3 → 5)

### Updated Metric Structure

```python
class EvalResult(BaseModel):
    # Core metrics (required by assignment)
    goal_completion: float            # 0-3
    conversational_quality: float     # 1-5 (now includes hallucination + tone)
    compliance: float                 # 0 or 1

    # Extended metrics (shows depth)
    response_consistency: float       # 0 or 1 (pass/fail)
    sentiment_shift: float            # -1.0 to +1.0 (negative = borrower got angrier)

    # Aggregate
    weighted_total: float

    # Detail
    turn_annotations: list[TurnAnnotation]
    hallucinations_found: list[str]   # NEW: specific hallucinations detected
    tone_assessment: str              # NEW: "appropriate" / "too aggressive" / "too passive" / etc.
    consistency_issues: list[str]     # NEW: specific contradictions found
```

### Updated Scoring Weights

```python
# config/settings.py — update:
SCORING_WEIGHTS = {
    "goal_completion": 0.35,       # was 0.5
    "conversational_quality": 0.15, # was 0.1
    "compliance": 0.30,            # was 0.4
    "response_consistency": 0.10,  # NEW
    "sentiment_shift": 0.10,       # NEW
}
```

### New/Updated Judge Implementations

#### Judge 2: Conversational Quality (UPDATED)

Add hallucination detection and tone match to the existing rubric:

```
Evaluate the agent's conversational competence across these dimensions:

REPETITION (-1 per instance, max -3):
  Does the agent repeat the same phrase or sentence more than once?
  Flag each instance with the turn number.

ACKNOWLEDGMENT (+1 per instance, max +3):
  Does the agent acknowledge what the borrower specifically said?
  (Not generic "I understand" but referencing their actual words/situation)

SPECIFICITY (+1 per instance, max +2):
  Does the agent offer specific solutions with concrete numbers?
  (Dollar amounts, dates, plan names — not vague "we have options")

TONE CONSISTENCY (+1 if maintained, 0 if breaks):       ← ENHANCED
  Does the agent maintain appropriate tone for the situation?
  - With angry borrower: should be calm, de-escalating (not matching anger OR being dismissive)
  - With hardship borrower: should be empathetic (not overly cheerful or dismissive)
  - With cooperative borrower: should be efficient and friendly (not overly formal)
  - With evasive borrower: should be persistent but respectful (not aggressive)
  Rate: "appropriate", "too_aggressive", "too_passive", "tone_mismatch"

HALLUCINATION CHECK (-2 per instance):                    ← NEW
  Does the agent make up facts not in its prompt?
  - Mentions specific payment programs that don't exist
  - States incorrect loan amounts, interest rates, or dates
  - Claims legal authority it doesn't have
  - Promises outcomes it can't guarantee (e.g., "this will clear your credit immediately")
  List each hallucination found.

Final score: 3 (baseline) + sum of adjustments, clamped to [1, 5]
Output: Score + flagged turns + hallucinations_found list + tone_assessment
```

#### Judge 4: Response Consistency (NEW)

```
Check if the AI agent contradicts itself during the conversation.

Look for:
- Agent states different loan amounts at different points
- Agent offers conflicting payment plan terms
- Agent says something is possible early on, then says it isn't later
- Agent repeats back borrower information incorrectly (name, amount, etc.)

Output: PASS (1.0) or FAIL (0.0) + list of specific contradictions found
```

#### Judge 5: Sentiment Shift (NEW)

```
Analyze how the BORROWER's sentiment changed during the conversation.

Assess the borrower's emotional state at:
- Start of conversation (first 3 turns)
- End of conversation (last 3 turns)

Score:
  +1.0 = Borrower became significantly more positive/cooperative
  +0.5 = Borrower became somewhat more open
   0.0 = No change in sentiment
  -0.5 = Borrower became somewhat more hostile/closed off
  -1.0 = Borrower became significantly more angry/hostile

This measures the agent's ability to de-escalate and build rapport.
Output: Score (-1.0 to +1.0) + brief explanation
```

### Updated Aggregate Scoring

```python
# evaluation/scorer.py — update:

def compute_weighted_total(eval_result: EvalResult) -> float:
    weights = SCORING_WEIGHTS

    # Normalize all metrics to 0-1 range for weighted sum
    normalized = {
        "goal_completion": eval_result.goal_completion / 3.0,         # 0-3 → 0-1
        "conversational_quality": (eval_result.conversational_quality - 1) / 4.0,  # 1-5 → 0-1
        "compliance": eval_result.compliance,                          # already 0-1
        "response_consistency": eval_result.response_consistency,      # already 0-1
        "sentiment_shift": (eval_result.sentiment_shift + 1) / 2.0,   # -1 to +1 → 0-1
    }

    total = sum(normalized[k] * weights[k] for k in weights)
    return round(total * 5.0, 2)  # Scale back to 0-5 for readability
```

---

## 4. Streamlit UI

### New File: app.py (root level)

The Streamlit app reads from MongoDB and provides visual interaction. It does NOT contain business logic — it calls existing modules.

### Page Structure

```
Sidebar:
  - App title: "Darwin-Gödel Voice Agent"
  - Navigation: Personas | Evolution | Conversations | Archive | Voice Agent

Page 1: PERSONAS
  - Display 5 persona cards (archetype, description, sample backstory)
  - Each card has a "Run Simulation" button
  - When clicked:
    - Dropdown to select agent version (default: champion)
    - Starts simulation, shows live transcript updating turn-by-turn
    - After completion: shows eval scores inline
    - Conversation auto-saved to MongoDB

Page 2: EVOLUTION DASHBOARD
  - "Start Evolution" button (triggers evolution loop)
    - Config inputs: max_generations, threshold, conversations_per_persona
  - Progress display during run (current generation, current phase)
  - Score progression chart (line chart: generation vs score, one line per persona + aggregate)
  - Current champion info: version ID, generation, aggregate score
  - Termination reason (if completed)

Page 3: CONVERSATIONS
  - Filters at top:
    - Agent Version: [dropdown, all versions]
    - Persona Type: [dropdown: all, angry, evasive, hardship, informed, cooperative]
    - Source: [dropdown: all, simulation, voice_live]
    - Outcome: [dropdown: all, success, rejection, hallucination, timeout]
  - Table of conversations matching filters:
    - Columns: ID, Version, Persona, Source, Outcome, Goal Score, Quality Score, Compliance, Timestamp
    - Click a row → expands to show:
      - Full turn-by-turn transcript
      - Annotations highlighted inline (⚠️ icons for flagged turns)
      - Eval result breakdown (all 5 metrics)
      - Metadata (model, tokens, duration)

Page 4: AGENT ARCHIVE
  - Evolution tree visualization (use streamlit-agraph or simple indented tree)
  - Table of all versions:
    - Columns: ID, Parent, Generation, Mutation Target, Rationale (truncated), Aggregate Score, Status
    - Status badges: 🟢 promoted, 🔴 archived, 🔵 base
  - Click a version → expands to show:
    - Full prompt sections
    - Prompt diff from parent (highlighted: green=added, red=removed)
    - Failure patterns that motivated this mutation
    - Per-persona score breakdown
    - Link to conversations for this version

Page 5: VOICE AGENT
  - "Start Voice Agent" button
    - Select version (default: champion)
    - Launches Pipecat pipeline via subprocess
    - Shows connection info (localhost URL for WebRTC)
    - Or embed the WebRTC client directly if possible
  - Below: list of live voice conversations (source: "voice_live")
```

### Implementation Notes for app.py

```python
# app.py — rough structure (~300-400 lines)

import streamlit as st
from core.db import agent_versions_collection, conversations_collection
from core.models import AgentVersion, Conversation
from simulation.conversation import simulate_conversation
from evaluation.judges import evaluate_conversation
from evolution.loop import run_evolution
from config.personas import PERSONA_ARCHETYPES, randomize_persona
from core.prompt_builder import build_prompt

st.set_page_config(page_title="Darwin-Gödel Voice Agent", layout="wide")

page = st.sidebar.radio("Navigation", [
    "🎭 Personas",
    "🧬 Evolution",
    "💬 Conversations",
    "📦 Archive",
    "🎙️ Voice Agent"
])

if page == "🎭 Personas":
    render_personas_page()
elif page == "🧬 Evolution":
    render_evolution_page()
# ... etc

def render_personas_page():
    st.header("Test Personas")
    cols = st.columns(5)
    for i, (archetype, config) in enumerate(PERSONA_ARCHETYPES.items()):
        with cols[i]:
            st.subheader(archetype.title())
            st.write(config["description"])
            if st.button(f"Simulate", key=f"sim_{archetype}"):
                run_single_simulation(archetype)

def run_single_simulation(archetype: str):
    """Run one simulation and display results live."""
    version = get_champion()  # or let user select
    persona_config = randomize_persona(archetype)
    prompt = build_prompt(version.prompt_sections)

    # Show live transcript
    transcript_container = st.empty()
    turns = []

    # Run simulation with callback for live updates
    conversation = simulate_conversation(
        agent_prompt=prompt,
        persona_config=persona_config,
        on_turn=lambda turn: update_live_transcript(transcript_container, turns, turn)
    )

    # Evaluate
    eval_result = evaluate_conversation(conversation)
    conversation.eval_result = eval_result
    save_conversation(conversation)

    # Show scores
    display_eval_scores(eval_result)

def render_conversations_page():
    st.header("Conversation Logs")

    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        version_filter = st.selectbox("Version", ["All"] + get_version_ids())
    with col2:
        persona_filter = st.selectbox("Persona", ["All", "angry", "evasive", "hardship", "informed", "cooperative"])
    with col3:
        source_filter = st.selectbox("Source", ["All", "simulation", "voice_live"])
    with col4:
        outcome_filter = st.selectbox("Outcome", ["All", "success", "rejection", "hallucination", "timeout"])

    # Build query and fetch
    conversations = get_conversations_filtered(...)

    # Display table
    for conv in conversations:
        with st.expander(f"{conv.id} | {conv.persona_type} | {conv.outcome} | Score: {conv.eval_result.weighted_total}"):
            display_conversation_transcript(conv)
            display_eval_breakdown(conv.eval_result)
```

### Streamlit Dependencies

```
# Add to pyproject.toml / requirements.txt:
streamlit>=1.30.0
streamlit-agraph>=0.0.45    # optional: for tree visualization
plotly>=5.18.0              # for charts (or use st.line_chart which needs nothing)
```

---

## 5. Pipecat Voice Pipeline Corrections

### CRITICAL: Use Built-in Services, Not Custom

**WRONG** (what we had before):
```python
class DebtCollectorLLMService:
    async def process_frame(self, frame):
        # Custom frame processing
```

**CORRECT** (what Pipecat actually provides):
```python
from pipecat.services.openai import OpenAILLMService
from pipecat.services.openai import OpenAILLMContext
from pipecat.transports.services.helpers.daily_rest import SmallWebRTCTransport
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.cartesia import CartesiaTTSService
# OR
from pipecat.services.elevenlabs import ElevenLabsTTSService
```

### Correct Pipeline Assembly

```python
# voice/pipeline.py

import asyncio
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.openai import OpenAILLMService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.transports.network.small_webrtc_transport import SmallWebRTCTransport

from core.archive import get_version
from core.prompt_builder import build_prompt

async def run_voice_agent(version_id: str, host: str = "0.0.0.0", port: int = 8765):
    """Start the voice agent with a specific prompt version."""

    # Load evolved prompt from archive
    agent_version = get_version(version_id)
    system_prompt = build_prompt(agent_version.prompt_sections)

    # Set up transport (browser-based WebRTC, works locally)
    transport = SmallWebRTCTransport(
        host=host,
        port=port
    )

    # STT: Deepgram
    stt = DeepgramSTTService(
        api_key=DEEPGRAM_API_KEY,
    )

    # LLM: OpenAI with evolved system prompt
    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        model="gpt-4o"
    )

    # TTS: Cartesia
    tts = CartesiaTTSService(
        api_key=CARTESIA_API_KEY,
        voice_id="...",  # choose appropriate voice
    )

    # Context with system prompt from evolved agent
    context = OpenAILLMContext(
        messages=[
            {"role": "system", "content": system_prompt},
        ]
    )
    context_aggregator = llm.create_context_aggregator(context)

    # Assemble pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant()
    ])

    task = PipelineTask(pipeline, PipelineParams(
        allow_interruptions=True,
        enable_metrics=True,
    ))

    runner = PipelineRunner()
    await runner.run(task)
```

### Voice Conversation Logging

**IMPORTANT**: We need to capture voice conversations and save them to MongoDB too.

Add an event handler to the pipeline that logs turns:

```python
# In voice/pipeline.py — add conversation logging

from core.db import save_conversation
from core.models import Conversation, Turn

class ConversationLogger:
    """Captures turns from the voice pipeline for storage."""
    def __init__(self, version_id: str):
        self.version_id = version_id
        self.turns = []
        self.turn_index = 0

    def on_user_transcript(self, text: str):
        self.turns.append(Turn(
            index=self.turn_index,
            role="borrower",
            content=text,
            timestamp=datetime.utcnow()
        ))
        self.turn_index += 1

    def on_agent_response(self, text: str):
        self.turns.append(Turn(
            index=self.turn_index,
            role="agent",
            content=text,
            timestamp=datetime.utcnow()
        ))
        self.turn_index += 1

    def save(self):
        conv = Conversation(
            id=f"voice_{uuid4().hex[:8]}",
            agent_version_id=self.version_id,
            persona_type=None,           # Real human, no persona
            persona_config=None,
            source="voice_live",          # Mark as live voice
            turns=self.turns,
            outcome="ended_by_user",
            duration_turns=len(self.turns),
            eval_result=None,             # Can be evaluated later from UI
            metadata=ConversationMetadata(model_used="gpt-4o"),
            created_at=datetime.utcnow()
        )
        save_conversation(conv)
        return conv.id
```

### Browser Client

SmallWebRTCTransport serves a WebRTC endpoint. The user opens a browser to connect. We need a simple HTML client page:

```
voice/
├── __init__.py
├── pipeline.py              # Pipecat pipeline assembly + conversation logger
└── client.html              # Simple WebRTC client page (served by transport or separately)
```

**NOTE**: Before implementing, check the latest Pipecat docs and examples for SmallWebRTCTransport usage. The API may have specific requirements for the client page. Look at: https://github.com/pipecat-ai/pipecat/tree/main/examples

---

## 6. Two UI Modes for Interaction

### Mode 1: Simulate (from Streamlit UI)

- User selects a persona + agent version from the UI
- System runs text-based simulation (LLM ↔ LLM)
- Live transcript shown in Streamlit
- Auto-evaluated after completion
- Saved with `source: "simulation"`

### Mode 2: Talk to Agent (Voice via Pipecat)

- User selects agent version from Streamlit
- Streamlit launches Pipecat voice server via subprocess
- Shows connection URL (e.g., `http://localhost:8765`)
- User opens browser, speaks via microphone
- Conversation captured by ConversationLogger
- Saved with `source: "voice_live"`, `persona_type: null`
- Can be evaluated later from the Conversations page ("Evaluate" button)

### Triggering Voice from Streamlit

```python
# In app.py, Voice Agent page:

def render_voice_page():
    st.header("🎙️ Voice Agent")

    version_id = st.selectbox("Agent Version", get_version_ids(), index=get_champion_index())

    if st.button("Start Voice Agent"):
        # Launch Pipecat in subprocess
        import subprocess
        process = subprocess.Popen(
            ["python", "-m", "voice.pipeline", "--version", version_id],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        st.success(f"Voice agent started! Open **http://localhost:8765** in your browser to talk.")
        st.info("Speak into your microphone. The conversation will be logged automatically.")

    # Show past voice conversations
    st.subheader("Voice Conversation History")
    voice_convos = get_conversations_filtered(source="voice_live")
    for conv in voice_convos:
        with st.expander(f"{conv.id} | {conv.created_at} | Turns: {conv.duration_turns}"):
            display_conversation_transcript(conv)
            if conv.eval_result:
                display_eval_breakdown(conv.eval_result)
            else:
                if st.button(f"Evaluate", key=f"eval_{conv.id}"):
                    eval_result = evaluate_conversation(conv)
                    conv.eval_result = eval_result
                    save_conversation(conv)
                    st.rerun()
```

---

## 7. Updated File Structure

```
darwin-godel-voice-agent/
│
├── README.md
├── pyproject.toml
├── .env.example
├── app.py                           # Streamlit UI (~300-400 lines)
├── main.py                          # CLI entrypoint: evolution loop + report
│
├── config/
│   ├── __init__.py
│   ├── settings.py                  # All config + MONGO_URI + scoring weights
│   ├── personas.py                  # 5 archetypes + randomization
│   └── base_prompt.py               # Base v0 prompt as Python dict
│
├── core/
│   ├── __init__.py
│   ├── models.py                    # All Pydantic models (updated with source, metadata, new metrics)
│   ├── db.py                        # NEW: MongoDB connection + collection references
│   ├── archive.py                   # Archive CRUD via MongoDB (updated from JSON)
│   ├── prompt_builder.py            # Assembles sections → full prompt
│   └── llm_client.py               # LLM wrapper (retries, model routing, cost tracking)
│
├── simulation/
│   ├── __init__.py
│   └── conversation.py              # Turn-by-turn engine + termination + batch runner
│                                    # Now accepts optional on_turn callback for live UI updates
│
├── evaluation/
│   ├── __init__.py
│   ├── judges.py                    # 5 judges (goal, quality+hallucination+tone, compliance,
│   │                                #           response_consistency, sentiment_shift)
│   └── scorer.py                    # Aggregation with updated weights
│
├── evolution/
│   ├── __init__.py
│   ├── failure_analyzer.py
│   ├── mutator.py
│   ├── selector.py
│   └── loop.py
│
├── voice/
│   ├── __init__.py
│   ├── pipeline.py                  # Pipecat: SmallWebRTCTransport + OpenAILLMService
│   │                                #          + ConversationLogger
│   └── client.html                  # WebRTC client page (if not provided by Pipecat)
│
├── report.py                        # Static HTML report generator (for GitHub repo)
│
├── scripts/
│   └── export_json.py               # Dumps MongoDB to JSON for GitHub submission
│
├── data/                            # JSON exports (for GitHub repo, generated by export script)
│   ├── archive/
│   ├── conversations/
│   └── reports/
│
└── tests/
    ├── test_simulation.py
    ├── test_evaluation.py
    └── test_archive.py
```

**Total substantive files: ~20** (including `__init__.py`). Each under 300-400 lines.

---

## 8. Conversation Evaluation: What Gets Scored

### For Simulated Conversations (automatic)

All 5 metrics scored immediately after simulation completes:
1. Goal Completion (0-3)
2. Conversational Quality (1-5) — includes repetition, acknowledgment, specificity, tone, hallucination
3. Compliance (pass/fail)
4. Response Consistency (pass/fail)
5. Sentiment Shift (-1.0 to +1.0)

### For Voice Conversations (on-demand)

Voice conversations are saved without eval scores initially. User can click "Evaluate" in the Conversations page to run the 5 judges on the transcript. This makes sense because:
- The transcript is captured from STT (may have transcription artifacts)
- Some metrics (like goal completion) may not apply if the user was just testing casually
- The user might want to evaluate with a specific rubric or skip evaluation

---

## 9. README Section on Language

Add this to the README:

```markdown
## Language Support

The current implementation uses English for all agent prompts, persona simulations,
and evaluations. The architecture is language-agnostic — adding Hindi/Hinglish support
requires only:

1. Translating persona prompts in `config/personas.py`
2. Selecting appropriate TTS voices (e.g., ElevenLabs Multilingual V2)
3. Ensuring STT model supports the target language (Deepgram supports Hindi)
4. Updating evaluation judge prompts to evaluate in the target language

No architectural changes needed — the evolution loop, archive, and evaluation
framework work identically regardless of language.
```

---

## 10. Pre-Implementation Checklist

Before starting implementation of these changes:

- [ ] **Verify Pipecat API**: Check latest Pipecat docs for `SmallWebRTCTransport`, `OpenAILLMService`, `OpenAILLMContext` exact usage. Look at examples: https://github.com/pipecat-ai/pipecat/tree/main/examples
- [ ] **MongoDB running**: Ensure local MongoDB is accessible at `localhost:27017`
- [ ] **API keys ready**: OpenAI, Deepgram, Cartesia (or ElevenLabs) in `.env`
- [ ] **Streamlit installed**: `pip install streamlit`
- [ ] **Test MongoDB connection**: Quick `pymongo` test before building archive layer

---

## 11. Implementation Priority

1. **`core/db.py`** + update `core/archive.py` → MongoDB layer
2. **`core/models.py`** → Add source, metadata, new metric fields
3. **`evaluation/judges.py`** → Add hallucination, tone, consistency, sentiment judges
4. **`evaluation/scorer.py`** → Updated weights and normalization
5. **`simulation/conversation.py`** → Add `on_turn` callback for live UI
6. **`app.py`** → Streamlit UI (personas, evolution, conversations, archive pages)
7. **`voice/pipeline.py`** → Corrected Pipecat integration
8. **`scripts/export_json.py`** → JSON export for GitHub
9. **`report.py`** → Static HTML report
10. **Integration testing** → Run full evolution loop through Streamlit

---

## 12. Key Reminders

- **Every conversation gets saved** — simulated or live, always to MongoDB with full turns + metadata
- **Every conversation has a `source` field** — "simulation" or "voice_live"
- **Live voice conversations have `persona_type: null`** — real humans aren't personas
- **Evaluation is automatic for simulations, on-demand for voice** — button in UI
- **Evolution loop writes to MongoDB** — Streamlit reads from same MongoDB
- **JSON export is for GitHub submission only** — not the primary storage
- **Check Pipecat docs before implementing voice** — don't assume API, verify it
- **Tone evaluation is text-based** — analyzing word choice and linguistic register, not audio pitch
- **Hallucination detection compares agent statements against the prompt** — if the prompt doesn't mention a "hardship program", and the agent promises one, that's a hallucination

---

*This document supplements the original SYSTEM_DESIGN.md. Both should be read together.*
*Last updated: March 2026*