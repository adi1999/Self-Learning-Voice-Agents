# Pipecat Framework - Understanding & Notes

## What is Pipecat?
Pipecat is an open-source Python framework by Daily.co for building real-time voice and multimodal conversational AI agents. It achieves 500-800ms end-to-end latency for natural voice conversations.

## Core Architecture: Pipeline
Audio/text flows through a chain of processors:
```
Transport (mic) → STT → LLM → TTS → Transport (speaker)
```

Each stage is a processor in the pipeline. Pipecat orchestrates them with real-time streaming.

## Key Components

### Transports (how audio gets in/out)
| Transport | Use Case |
|-----------|----------|
| **SmallWebRTCTransport** | Direct peer-to-peer WebRTC, no cloud infra needed — best for local dev |
| DailyTransport | WebRTC via Daily's infrastructure |
| FastAPIWebsocketTransport | WebSocket for telephony |
| LiveKitTransport | WebRTC via LiveKit |
| WebsocketTransport | General-purpose WebSocket |

Each transport has `input()` and `output()` methods that plug into the pipeline.

### Speech-to-Text (STT) — 18+ providers
- **Deepgram** (recommended — generous free tier)
- OpenAI Whisper, Google Cloud, Azure, AssemblyAI, Speechmatics, Groq Whisper

### Language Models (LLM) — 15+ providers
- **OpenAI** (GPT-4o, GPT-4o-mini)
- Anthropic (Claude), Google Gemini, AWS Bedrock, Azure OpenAI
- Groq, Mistral, DeepSeek, Ollama (local)

### Text-to-Speech (TTS) — 20+ providers
- **Cartesia** (recommended — good free credits)
- **ElevenLabs** (high quality)
- OpenAI, Google Cloud, Azure, AWS Polly, Deepgram

### Speech-to-Speech (lower latency, skip STT+TTS)
- OpenAI Realtime, Gemini Live, AWS Nova Sonic

## Basic Voice Bot Setup

### Prerequisites
- Python 3.10+ (3.12 recommended)
- API keys: OpenAI, Deepgram, Cartesia (or ElevenLabs)

### Installation
```bash
pip install "pipecat-ai[openai,deepgram,cartesia,smallwebrtc,silero]"
```

Extras are modular — only install what you need. `silero` is for voice activity detection (VAD).

### Minimal Bot Pattern
```python
import os
from pipecat.pipeline.pipeline import Pipeline
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.transports.services.helpers.smallwebrtc import SmallWebRTCTransport

async def run_bot(webrtc_transport):
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini"
    )
    # System prompt is set via messages context

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="...",
    )

    pipeline = Pipeline([
        webrtc_transport.input(),   # mic audio in
        stt,                        # speech → text
        llm,                        # text → response text
        tts,                        # response text → speech
        webrtc_transport.output(),  # speaker audio out
    ])

    # Run the pipeline
    task = PipelineTask(pipeline)
    await task.run()
```

### Server Pattern (FastAPI + WebRTC)
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pipecat.transports.services.helpers.smallwebrtc import SmallWebRTCTransport

app = FastAPI()

@app.post("/api/offer")
async def offer(request: Request):
    # Handle WebRTC offer/answer exchange
    ...

# Serve index.html for browser client
app.mount("/", StaticFiles(directory=".", html=True))

# Run: uvicorn server:app --host 0.0.0.0 --port 7860
```

The browser client (`index.html`) uses the Pipecat JS client SDK to establish the WebRTC connection.

### Conversation Context
The LLM's system prompt and conversation history are managed via a messages context:
```python
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

context = OpenAILLMContext(
    messages=[
        {"role": "system", "content": "You are a debt collection agent..."}
    ]
)
context_aggregator = llm.create_context_aggregator(context)

pipeline = Pipeline([
    transport.input(),
    context_aggregator.user(),    # aggregates user speech
    llm,
    tts,
    transport.output(),
    context_aggregator.assistant() # aggregates assistant responses
])
```

This is how we plug in the evolved prompt — just change the system message content.

## Key Takeaways for This Project
1. **Only the system prompt changes** — the pipeline (STT → LLM → TTS) stays the same across all agent versions
2. **SmallWebRTCTransport** is ideal for local demo — no cloud infra needed
3. **Text simulation doesn't need Pipecat** — we use OpenAI API directly for the evolution loop, Pipecat is only for the final voice demo
4. **Conversation context** is where the evolved prompt gets injected
5. **VAD (silero)** handles turn-taking automatically — detects when user stops speaking

## Resources
- GitHub: https://github.com/pipecat-ai/pipecat
- Docs: https://docs.pipecat.ai/
- Quickstart: https://docs.pipecat.ai/getting-started/quickstart
- P2P WebRTC example: https://github.com/pipecat-ai/pipecat-examples/tree/main/p2p-webrtc/voice-agent
- macOS local voice agents: https://github.com/kwindla/macos-local-voice-agents