"""Streamlit UI for the Darwin-Godel Voice Agent platform."""

import asyncio
import logging
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

import streamlit as st
import plotly.graph_objects as go

from config.personas import randomize_persona
from config.settings import (
    PERSONA_ARCHETYPES, CONVERSATIONS_PER_PERSONA, SCORE_THRESHOLD,
    MAX_GENERATIONS, BASE_PROMPT_PATH,
)
from core.archive import (
    get_champion,
    get_conversations_filtered,
    get_evolution_runs,
    get_versions_by_run,
    list_versions,
    load_version,
    save_conversation,
    save_version,
)
from core.models import AgentVersion, Conversation
from core.prompt_builder import build_prompt, load_base_prompt
from dashboard.streamlit_helpers import (
    display_eval_breakdown,
    display_transcript,
    format_score_badge,
    format_status_badge,
)

st.set_page_config(page_title="Darwin-Godel Voice Agent", layout="wide")


def _ensure_v0() -> None:
    """Seed v0 into MongoDB from base_v0.yaml if no versions exist."""
    if list_versions():
        return
    sections = load_base_prompt(BASE_PROMPT_PATH)
    v0 = AgentVersion(
        id="v0",
        generation=0,
        prompt_sections=sections,
        status="base",
    )
    save_version(v0)


_ensure_v0()

page = st.sidebar.radio("Navigation", [
    "Personas",
    "Evolution",
    "Conversations",
    "Archive",
    "Voice Agent",
])


def _get_version_ids() -> list[str]:
    return [v.id for v in list_versions()]


def _run_async(coro):
    """Run an async coroutine from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _run_single_simulation(archetype: str, version_id: str) -> None:
    """Run a single persona simulation and display results."""
    from simulation.conversation import simulate_conversation
    from evaluation.scorer import evaluate_conversation

    agent_version = load_version(version_id)
    persona_config = randomize_persona(archetype)
    agent_prompt = build_prompt(agent_version.prompt_sections)

    transcript_container = st.empty()
    displayed_turns = []

    def on_turn(turn):
        displayed_turns.append(turn)
        with transcript_container.container():
            for t in displayed_turns:
                role_label = "Agent" if t.role == "agent" else "Borrower"
                st.markdown(f"**{role_label}:** {t.content}")

    with st.spinner("Running simulation..."):
        conversation = _run_async(simulate_conversation(
            agent_prompt=agent_prompt,
            persona_config=persona_config,
            version_id=version_id,
            run_number=999,
            on_turn=on_turn,
        ))

    with st.spinner("Evaluating..."):
        _run_async(evaluate_conversation(conversation))
        save_conversation(conversation)

    st.success(f"Outcome: {conversation.outcome}")
    if conversation.eval_result:
        display_eval_breakdown(conversation.eval_result)


# ============================================================
# Page 1: Personas
# ============================================================
if page == "Personas":
    st.header("Test Personas")

    version_ids = _get_version_ids()
    champ = get_champion()
    default_idx = 0
    if champ and version_ids and champ.id in version_ids:
        default_idx = version_ids.index(champ.id)
    selected_version = st.selectbox(
        "Agent Version",
        version_ids if version_ids else ["(none)"],
        index=default_idx,
    )

    cols = st.columns(5)
    persona_descriptions = {
        "angry": "Hostile, questions legitimacy, threatens RBI complaint.",
        "evasive": "Dodges questions, never commits, polite but slippery.",
        "hardship": "Genuine financial difficulty, emotional, needs empathy.",
        "informed": "Knows RBI guidelines, cites SARFAESI, calm and methodical.",
        "cooperative": "Willing to pay, asks about EMI plans, easiest persona.",
    }

    for i, archetype in enumerate(PERSONA_ARCHETYPES):
        with cols[i]:
            st.subheader(archetype.title())
            st.caption(persona_descriptions.get(archetype, ""))
            if st.button("Simulate", key=f"sim_{archetype}"):
                if selected_version == "(none)":
                    st.error("No agent versions found. Run evolution first.")
                else:
                    _run_single_simulation(archetype, selected_version)

    # --- Run All 5 Personas ---
    st.divider()
    if st.button("Run All 5 Personas", type="primary"):
        if selected_version == "(none)":
            st.error("No agent versions found. Run evolution first.")
        else:
            from simulation.conversation import simulate_conversation
            from evaluation.scorer import evaluate_conversation

            agent_version = load_version(selected_version)
            agent_prompt = build_prompt(agent_version.prompt_sections)
            results_container = st.container()

            for archetype in PERSONA_ARCHETYPES:
                persona_config = randomize_persona(archetype)
                with results_container:
                    st.markdown(f"---")
                    st.subheader(f"{archetype.title()}: {persona_config.name}")
                    st.caption(f"${persona_config.loan_amount:,.2f} | {persona_config.months_overdue} months overdue | {persona_config.backstory[:80]}...")

                    with st.spinner(f"Simulating {archetype}..."):
                        conversation = _run_async(simulate_conversation(
                            agent_prompt=agent_prompt,
                            persona_config=persona_config,
                            version_id=selected_version,
                            run_number=888,
                        ))

                    with st.spinner(f"Evaluating {archetype}..."):
                        _run_async(evaluate_conversation(conversation))
                        save_conversation(conversation)

                    st.success(f"Outcome: {conversation.outcome}")
                    if conversation.eval_result:
                        display_eval_breakdown(conversation.eval_result)
                    with st.expander("View Transcript"):
                        display_transcript(conversation)


# ============================================================
# Page 2: Evolution
# ============================================================
elif page == "Evolution":
    st.header("Evolution Dashboard")

    # --- Start New Run ---
    st.subheader("Start New Evolution Run")
    col1, col2, col3 = st.columns(3)
    with col1:
        max_gen = st.number_input("Max Generations", 1, 20, MAX_GENERATIONS)
    with col2:
        threshold = st.number_input("Score Threshold", 1.0, 5.0, SCORE_THRESHOLD, step=0.1)
    with col3:
        convos_per = st.number_input("Conversations/Persona", 1, 10, CONVERSATIONS_PER_PERSONA)

    current_champion = get_champion()
    has_champion = current_champion is not None and current_champion.scores is not None
    start_from = st.radio(
        "Start from",
        ["Champion (recommended)", "Base prompt"],
        index=0 if has_champion else 1,
        horizontal=True,
    )
    if has_champion and start_from == "Champion (recommended)":
        st.caption(f"Will evolve from **{current_champion.id}** (score: {current_champion.scores.aggregate:.2f})")
    else:
        st.caption("Will start fresh from base_v0.yaml")

    if st.button("Start Evolution"):
        from evolution.loop import run_evolution

        start_sections = None
        if has_champion and start_from == "Champion (recommended)":
            start_sections = current_champion.prompt_sections

        progress_container = st.empty()
        progress_log = []

        def on_progress(data):
            progress_log.append(data)
            with progress_container.container():
                for entry in progress_log[-10:]:
                    gen = entry.get("generation", "?")
                    phase = entry.get("phase", "")
                    msg = entry.get("message", "")
                    score = entry.get("score")
                    line = f"Gen {gen} | {phase}"
                    if msg:
                        line += f" | {msg}"
                    if score is not None:
                        line += f" | Score: {score:.2f}"
                    st.text(line)

        with st.spinner("Evolution running..."):
            champion = _run_async(run_evolution(
                max_generations=max_gen,
                threshold=threshold,
                conversations_per_persona=convos_per,
                on_progress=on_progress,
                start_sections=start_sections,
            ))

        st.success(f"Champion: {champion.id} (score: {champion.scores.aggregate:.2f})")
        st.rerun()

    # --- Past Runs ---
    st.divider()
    st.subheader("Evolution Run History")

    runs = get_evolution_runs()
    if not runs:
        st.info("No evolution runs yet. Start one above.")
    else:
        for run in runs:
            run_id = run["id"]
            gens = run.get("generations_completed", 0)
            final = run.get("final_score", 0)
            reason = run.get("termination_reason", "unknown")
            champ = run.get("champion_id", "?")
            start = run.get("start_time", "")[:19].replace("T", " ")

            is_incomplete = reason in ("in_progress", "unknown")
            status_icon = "..." if is_incomplete else ""
            label = f"{run_id} | {start} | {gens} gens | Champion: {champ} | Score: {final:.2f} | {reason} {status_icon}"

            with st.expander(label):
                gen_log = run.get("generation_log", [])
                all_vid = run.get("all_version_ids", [])

                # Resume button for incomplete runs
                if is_incomplete:
                    st.warning("This run did not complete.")
                    if st.button("Resume This Run", key=f"resume_{run_id}"):
                        from evolution.loop import run_evolution as _resume_evo

                        resume_progress = st.empty()
                        resume_log = []

                        def on_resume_progress(data, _log=resume_log, _container=resume_progress):
                            _log.append(data)
                            with _container.container():
                                for entry in _log[-10:]:
                                    g = entry.get("generation", "?")
                                    phase = entry.get("phase", "")
                                    msg = entry.get("message", "")
                                    sc = entry.get("score")
                                    line = f"Gen {g} | {phase}"
                                    if msg:
                                        line += f" | {msg}"
                                    if sc is not None:
                                        line += f" | Score: {sc:.2f}"
                                    st.text(line)

                        with st.spinner("Resuming evolution..."):
                            resumed_champ = _run_async(_resume_evo(
                                max_generations=max_gen,
                                threshold=threshold,
                                conversations_per_persona=convos_per,
                                on_progress=on_resume_progress,
                                resume_run_id=run_id,
                            ))
                        st.success(f"Champion: {resumed_champ.id} (score: {resumed_champ.scores.aggregate:.2f})")
                        st.rerun()

                # Summary
                st.markdown(f"**Versions created:** {len(all_vid)} ({', '.join(all_vid)})")
                st.markdown(f"**Termination:** {reason}")

                # Per-generation table
                if gen_log:
                    st.markdown("**Generation Log:**")
                    for entry in gen_log:
                        g = entry["generation"]
                        sc = entry["score"]
                        tested = ", ".join(entry.get("versions_tested", []))
                        promoted = entry.get("promoted")
                        mutation = entry.get("mutation_target") or "-"
                        prom_str = f" -> Promoted **{promoted}**" if promoted else " -> No improvement"
                        if g == 0:
                            st.markdown(f"- **Gen {g}** (baseline): score={sc:.2f} | {tested}")
                        else:
                            st.markdown(f"- **Gen {g}**: mutated [{mutation}] | tested: {tested} | score={sc:.2f}{prom_str}")

                # Score chart for this run — champion lineage only
                if gen_log and len(gen_log) > 1:
                    st.markdown("**Score Progression (champion only):**")
                    champion_ids = [entry["champion_id"] for entry in gen_log]
                    run_versions = get_versions_by_run(run_id)
                    version_map = {v.id: v for v in run_versions}

                    # Build chart from champion at each generation
                    chart_gens = [entry["generation"] for entry in gen_log]
                    chart_agg = [entry["score"] for entry in gen_log]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=chart_gens, y=chart_agg,
                        mode="lines+markers", name="Aggregate",
                        line=dict(width=3),
                    ))

                    for persona in PERSONA_ARCHETYPES:
                        y_vals = []
                        for entry in gen_log:
                            v = version_map.get(entry["champion_id"])
                            if v and v.scores and persona in v.scores.per_persona:
                                y_vals.append(v.scores.per_persona[persona].weighted_total)
                            else:
                                y_vals.append(None)
                        fig.add_trace(go.Scatter(
                            x=chart_gens, y=y_vals,
                            mode="lines+markers", name=persona.title(),
                        ))

                    fig.update_layout(
                        xaxis_title="Generation", yaxis_title="Score",
                        xaxis=dict(dtick=1),
                        height=350, margin=dict(l=40, r=40, t=20, b=40),
                    )
                    st.plotly_chart(fig, width="stretch")


# ============================================================
# Page 3: Conversations
# ============================================================
elif page == "Conversations":
    st.header("Conversation Logs")

    col1, col2, col3, col4 = st.columns(4)
    version_ids = _get_version_ids()
    with col1:
        ver_filter = st.selectbox("Version", ["All"] + version_ids)
    with col2:
        persona_filter = st.selectbox("Persona", ["All"] + PERSONA_ARCHETYPES)
    with col3:
        source_filter = st.selectbox("Source", ["All", "simulation", "voice_live"])
    with col4:
        outcome_filter = st.selectbox("Outcome", ["All", "success", "rejection", "hallucination", "timeout", "ended_by_user"])

    conversations = get_conversations_filtered(
        version_id=ver_filter if ver_filter != "All" else None,
        persona_type=persona_filter if persona_filter != "All" else None,
        source=source_filter if source_filter != "All" else None,
        outcome=outcome_filter if outcome_filter != "All" else None,
    )

    st.caption(f"{len(conversations)} conversations found")

    for conv in conversations:
        score_str = f"{conv.eval_result.weighted_total:.2f}" if conv.eval_result else "N/A"
        label = f"{conv.id} | {conv.persona_type or 'live'} | {conv.source} | {conv.outcome} | Score: {score_str}"
        with st.expander(label):
            display_transcript(conv)
            if conv.eval_result:
                display_eval_breakdown(conv.eval_result)
            else:
                if st.button("Evaluate", key=f"eval_{conv.id}"):
                    from evaluation.scorer import evaluate_conversation
                    with st.spinner("Evaluating..."):
                        _run_async(evaluate_conversation(conv))
                        save_conversation(conv)
                    st.rerun()


# ============================================================
# Page 4: Archive
# ============================================================
elif page == "Archive":
    st.header("Agent Version Archive")

    versions = list_versions()
    if not versions:
        st.info("No versions found. Run evolution first.")
    else:
        for v in versions:
            score_str = f"{v.scores.aggregate:.2f}" if v.scores else "N/A"
            status = format_status_badge(v.status)
            label = f"{status} {v.id} | Gen {v.generation} | Score: {score_str}"
            if v.mutation_target:
                label += f" | Mutated: {v.mutation_target}"

            with st.expander(label):
                if v.parent_id:
                    st.caption(f"Parent: {v.parent_id}")
                if v.rationale:
                    st.markdown(f"**Rationale:** {v.rationale}")
                if v.failure_patterns:
                    st.markdown("**Failure patterns:** " + ", ".join(v.failure_patterns))

                # Prompt sections
                st.subheader("Prompt Sections")
                for section, content in v.prompt_sections.items():
                    with st.expander(f"[{section}]", expanded=False):
                        st.code(content, language="text")

                # Diff from parent
                if v.parent_id and v.mutation_target:
                    try:
                        parent = load_version(v.parent_id)
                        old_text = parent.prompt_sections.get(v.mutation_target, "")
                        new_text = v.prompt_sections.get(v.mutation_target, "")
                        if old_text != new_text:
                            st.subheader(f"Diff: [{v.mutation_target}]")
                            st.text_area("Before", old_text, height=150, disabled=True, key=f"before_{v.id}")
                            st.text_area("After", new_text, height=150, disabled=True, key=f"after_{v.id}")
                    except ValueError:
                        pass

                # Per-persona scores
                if v.scores:
                    st.subheader("Per-Persona Scores")
                    score_data = []
                    for persona, ms in v.scores.per_persona.items():
                        score_data.append({
                            "Persona": persona.title(),
                            "Goal": f"{ms.goal_completion:.1f}",
                            "Quality": f"{ms.conversational_quality:.1f}",
                            "Compliance": f"{ms.compliance:.1f}",
                            "Consistency": f"{ms.response_consistency:.1f}",
                            "Sentiment": f"{ms.sentiment_shift:.2f}",
                            "Total": f"{ms.weighted_total:.2f}",
                        })
                    st.table(score_data)


# ============================================================
# Page 5: Voice Agent
# ============================================================
elif page == "Voice Agent":
    st.header("Voice Agent")

    version_ids = _get_version_ids()
    # Default to champion
    champ = get_champion()
    champ_idx = 0
    if champ and version_ids and champ.id in version_ids:
        champ_idx = version_ids.index(champ.id)
    selected = st.selectbox(
        "Agent Version",
        version_ids if version_ids else ["(none)"],
        index=champ_idx,
        key="voice_version",
    )

    if st.button("Start Voice Agent"):
        if selected == "(none)":
            st.error("No agent versions found.")
        else:
            process = subprocess.Popen(
                ["python", "scripts/run_voice.py", "--version", selected],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            st.session_state["voice_pid"] = process.pid
            st.success("Voice agent started! Open **http://localhost:8000** in your browser.")
            st.info("Speak into your microphone. The conversation will be logged automatically.")

    # Show past voice conversations
    st.subheader("Voice Conversation History")
    voice_convos = get_conversations_filtered(source="voice_live")
    if not voice_convos:
        st.caption("No voice conversations yet.")
    for conv in voice_convos:
        score_str = f"{conv.eval_result.weighted_total:.2f}" if conv.eval_result else "Not evaluated"
        with st.expander(f"{conv.id} | {conv.duration_turns} turns | {score_str}"):
            display_transcript(conv)
            if conv.eval_result:
                display_eval_breakdown(conv.eval_result)
            else:
                if st.button("Evaluate", key=f"voice_eval_{conv.id}"):
                    from evaluation.scorer import evaluate_conversation
                    with st.spinner("Evaluating..."):
                        _run_async(evaluate_conversation(conv))
                        save_conversation(conv)
                    st.rerun()
