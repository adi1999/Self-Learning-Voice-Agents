"""Display helpers for the Streamlit UI."""

import streamlit as st

from core.models import Conversation, EvalResult


def format_status_badge(status: str) -> str:
    """Return a status indicator for agent version status."""
    badges = {"promoted": "[PROMOTED]", "archived": "[ARCHIVED]", "base": "[BASE]"}
    return badges.get(status, status)


def format_score_badge(score: float | None) -> str:
    """Format a score for display."""
    if score is None:
        return "N/A"
    return f"{score:.2f}"


def display_transcript(conversation: Conversation) -> None:
    """Render a conversation transcript with annotation markers."""
    for turn in conversation.turns:
        role_label = "Agent" if turn.role == "agent" else "Borrower"
        prefix = f"**[{turn.index}] {role_label}:**"

        if turn.annotations:
            ann_text = " | ".join(f"{a.issue_type}: {a.description}" for a in turn.annotations)
            st.markdown(f"{prefix} {turn.content}")
            st.caption(f"  Annotations: {ann_text}")
        else:
            st.markdown(f"{prefix} {turn.content}")


def display_eval_breakdown(result: EvalResult) -> None:
    """Render evaluation scores in a compact layout."""
    compliance_str = "PASS" if result.compliance >= 1.0 else "FAIL"
    consistency_str = "PASS" if result.response_consistency >= 1.0 else "FAIL"

    st.markdown(
        f"| Goal | Quality | Compliance | Consistency | Sentiment | Total |\n"
        f"|:----:|:-------:|:----------:|:-----------:|:---------:|:-----:|\n"
        f"| **{result.goal_completion:.1f}**/3 "
        f"| **{result.conversational_quality:.1f}**/5 "
        f"| **{compliance_str}** "
        f"| **{consistency_str}** "
        f"| **{result.sentiment_shift:+.2f}** "
        f"| **{result.weighted_total:.2f}**/5 |"
    )

    if result.hallucinations_found:
        st.warning(f"Hallucinations: {', '.join(result.hallucinations_found)}")
    if result.consistency_issues:
        st.warning(f"Consistency issues: {', '.join(result.consistency_issues)}")
    if result.tone_assessment != "appropriate":
        st.info(f"Tone: {result.tone_assessment}")
