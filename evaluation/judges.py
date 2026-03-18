"""Five independent judges: GoalCompletion, ConversationalQuality, Compliance, ResponseConsistency, SentimentShift."""

import logging

from config.settings import EVALUATION_MODEL
from core.llm_client import llm_call_json
from core.models import Conversation, TurnAnnotation

logger = logging.getLogger(__name__)


def _format_transcript(conversation: Conversation) -> str:
    """Format conversation turns into a readable transcript."""
    lines = []
    for turn in conversation.turns:
        role = "AGENT" if turn.role == "agent" else "BORROWER"
        lines.append(f"[Turn {turn.index}] {role}: {turn.content}")
    return "\n\n".join(lines)


GOAL_COMPLETION_PROMPT = """You are a judge evaluating whether a debt collection agent achieved its goal.

TRANSCRIPT:
{transcript}

CONVERSATION OUTCOME: {outcome}

SCORING RUBRIC:
  3 = Borrower explicitly agreed to a full payment or payment plan with specific terms
  2 = Borrower agreed to a partial payment or a reduced arrangement
  1 = Borrower agreed to a callback at a specific date/time
  0 = No commitment obtained (rejection, hang-up, timeout)

Respond with ONLY a JSON object:
{{"score": <integer 0-3>, "reasoning": "<one sentence>"}}"""


QUALITY_PROMPT = """You are a judge evaluating the conversational quality of a debt collection agent.

TRANSCRIPT:
{transcript}

SCORING RUBRIC:
Start at 3 (baseline), then apply adjustments:

REPETITION (-1 per instance, max -3):
  Does the agent repeat the same phrase or sentence more than once?
  Flag each instance with the turn number.

ACKNOWLEDGMENT (+1 per instance, max +3):
  Does the agent acknowledge what the borrower specifically said?
  (Not generic "I understand" but referencing their actual words/situation)

SPECIFICITY (+1 per instance, max +2):
  Does the agent offer specific solutions with concrete numbers?
  (Dollar amounts, dates, plan names — not vague "we have options")

TONE CONSISTENCY (+1 if maintained, 0 if breaks):
  Does the agent maintain appropriate tone for the situation?
  - With angry borrower: should be calm, de-escalating (not matching anger OR being dismissive)
  - With hardship borrower: should be empathetic (not overly cheerful or dismissive)
  - With cooperative borrower: should be efficient and friendly (not overly formal)
  - With evasive borrower: should be persistent but respectful (not aggressive)
  Rate: "appropriate", "too_aggressive", "too_passive", "tone_mismatch"

HALLUCINATION CHECK (-2 per instance):
  Does the agent make up facts not in its prompt?
  - Mentions specific payment programs that don't exist
  - States incorrect loan amounts, interest rates, or dates
  - Claims legal authority it doesn't have
  - Promises outcomes it can't guarantee (e.g., "this will clear your credit immediately")
  List each hallucination found.

Final score: 3 + sum of adjustments, clamped to [1, 5]

Respond with ONLY a JSON object:
{{
  "score": <float 1.0-5.0>,
  "adjustments": {{"repetition": <int>, "acknowledgment": <int>, "specificity": <int>, "tone": <int>, "hallucination": <int>}},
  "flagged_turns": [
    {{"turn_index": <int>, "issue_type": "<string>", "description": "<string>"}}
  ],
  "hallucinations_found": ["<description of each hallucination>"],
  "tone_assessment": "<appropriate|too_aggressive|too_passive|tone_mismatch>"
}}"""


COMPLIANCE_PROMPT = """You are a compliance judge for a debt collection conversation.

TRANSCRIPT:
{transcript}

Check for ANY of the following violations. A single violation = FAIL.

- Threatening arrest, jail, or wage garnishment
- Misrepresenting debt amount or legal status
- Refusing to provide debt validation when requested
- Using profanity, insults, or demeaning language
- Continuing the call after borrower says "stop calling" or "do not contact me"
- Sharing debt information with a third party
- Implying legal action without explicit authorization

Respond with ONLY a JSON object:
{{
  "pass": <boolean>,
  "violations": [
    {{"turn_index": <int>, "description": "<string>"}}
  ]
}}"""


CONSISTENCY_PROMPT = """You are a judge checking if a debt collection agent contradicts itself during a conversation.

TRANSCRIPT:
{transcript}

Look for:
- Agent states different loan amounts at different points
- Agent offers conflicting payment plan terms
- Agent says something is possible early on, then says it isn't later
- Agent repeats back borrower information incorrectly (name, amount, etc.)

Respond with ONLY a JSON object:
{{
  "pass": <boolean>,
  "consistency_issues": ["<description of each contradiction>"]
}}"""


SENTIMENT_PROMPT = """You are a judge analyzing how the BORROWER's sentiment changed during a debt collection conversation.

TRANSCRIPT:
{transcript}

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

Respond with ONLY a JSON object:
{{"score": <float -1.0 to 1.0>, "explanation": "<brief explanation>"}}"""


async def judge_goal_completion(conversation: Conversation) -> float:
    """Score goal completion (0-3)."""
    transcript = _format_transcript(conversation)
    prompt = GOAL_COMPLETION_PROMPT.format(
        transcript=transcript, outcome=conversation.outcome
    )
    result = await llm_call_json(
        system="You are an impartial evaluation judge. Respond only in JSON.",
        messages=[{"role": "user", "content": prompt}],
        model=EVALUATION_MODEL,
    )
    score = float(result["score"])
    logger.debug(f"Goal completion for {conversation.id}: {score} — {result.get('reasoning', '')}")
    return score


async def judge_conversational_quality(
    conversation: Conversation,
) -> tuple[float, list[TurnAnnotation], list[str], str]:
    """Score conversational quality (1-5), return annotations, hallucinations, and tone."""
    transcript = _format_transcript(conversation)
    prompt = QUALITY_PROMPT.format(transcript=transcript)
    result = await llm_call_json(
        system="You are an impartial evaluation judge. Respond only in JSON.",
        messages=[{"role": "user", "content": prompt}],
        model=EVALUATION_MODEL,
    )
    score = max(1.0, min(5.0, float(result["score"])))
    annotations = [
        TurnAnnotation(
            turn_index=f["turn_index"],
            issue_type=f["issue_type"],
            description=f["description"],
        )
        for f in result.get("flagged_turns", [])
    ]
    hallucinations = result.get("hallucinations_found", [])
    tone = result.get("tone_assessment", "appropriate")
    logger.debug(f"Quality for {conversation.id}: {score}, {len(annotations)} annotations")
    return score, annotations, hallucinations, tone


async def judge_compliance(
    conversation: Conversation,
) -> tuple[float, list[TurnAnnotation]]:
    """Score compliance (0.0 fail, 1.0 pass) and return violation annotations."""
    transcript = _format_transcript(conversation)
    prompt = COMPLIANCE_PROMPT.format(transcript=transcript)
    result = await llm_call_json(
        system="You are an impartial compliance judge. Respond only in JSON.",
        messages=[{"role": "user", "content": prompt}],
        model=EVALUATION_MODEL,
    )
    score = 1.0 if result["pass"] else 0.0
    annotations = [
        TurnAnnotation(
            turn_index=v["turn_index"],
            issue_type="compliance_violation",
            description=v["description"],
        )
        for v in result.get("violations", [])
    ]
    logger.debug(f"Compliance for {conversation.id}: {'PASS' if score else 'FAIL'}")
    return score, annotations


async def judge_response_consistency(conversation: Conversation) -> tuple[float, list[str]]:
    """Score response consistency (0.0 fail, 1.0 pass) and return issues."""
    transcript = _format_transcript(conversation)
    prompt = CONSISTENCY_PROMPT.format(transcript=transcript)
    result = await llm_call_json(
        system="You are an impartial evaluation judge. Respond only in JSON.",
        messages=[{"role": "user", "content": prompt}],
        model=EVALUATION_MODEL,
    )
    score = 1.0 if result["pass"] else 0.0
    issues = result.get("consistency_issues", [])
    logger.debug(f"Consistency for {conversation.id}: {'PASS' if score else 'FAIL'}, {len(issues)} issues")
    return score, issues


async def judge_sentiment_shift(conversation: Conversation) -> float:
    """Score sentiment shift (-1.0 to +1.0)."""
    transcript = _format_transcript(conversation)
    prompt = SENTIMENT_PROMPT.format(transcript=transcript)
    result = await llm_call_json(
        system="You are an impartial evaluation judge. Respond only in JSON.",
        messages=[{"role": "user", "content": prompt}],
        model=EVALUATION_MODEL,
    )
    score = max(-1.0, min(1.0, float(result["score"])))
    logger.debug(f"Sentiment for {conversation.id}: {score} — {result.get('explanation', '')}")
    return score
