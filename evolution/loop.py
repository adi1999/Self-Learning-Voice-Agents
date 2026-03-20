"""Full evolution loop orchestrator with resume support."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from config.settings import (
    CONVERSATIONS_PER_PERSONA,
    IMMUTABLE_SECTIONS,
    MAX_GENERATIONS,
    PLATEAU_EPSILON,
    PLATEAU_WINDOW,
    PROMPT_SECTIONS,
    SCORE_THRESHOLD,
)
from core.archive import (
    get_versions_by_run,
    load_conversations,
    save_conversation,
    save_evolution_run,
    save_version,
)
from core.models import AgentVersion
from core.prompt_builder import load_base_prompt
from config.settings import BASE_PROMPT_PATH
from evaluation.scorer import evaluate_all
from evolution.failure_analyzer import analyze_failures
from evolution.mutator import generate_candidates
from evolution.selector import select_champion
from evolution.tactic_extractor import extract_tactics_from_conversations, record_failed_candidates
from simulation.persona_runner import run_full_evaluation_suite

logger = logging.getLogger(__name__)


def _version_id(run_id: str, generation: int, candidate_idx: int | None = None) -> str:
    """Generate unique version ID: {run_short}_v0, {run_short}_v1a, etc."""
    short = run_id.replace("run_", "")
    if generation == 0:
        return f"{short}_v0"
    suffix = chr(ord("a") + candidate_idx) if candidate_idx is not None else ""
    return f"{short}_v{generation}{suffix}"


def _rebuild_state_from_db(run_id: str) -> dict:
    """Rebuild evolution state from persisted data for resume."""
    versions = get_versions_by_run(run_id)
    if not versions:
        return {"found": False}

    version_map = {v.id: v for v in versions}
    scored = {v.id: v for v in versions if v.scores is not None}

    # Find v0
    short = run_id.replace("run_", "")
    v0_id = f"{short}_v0"
    v0 = version_map.get(v0_id)

    if not v0 or v0.id not in scored:
        return {"found": True, "v0_exists": v0 is not None, "v0_scored": False}

    # Find the current champion (highest gen promoted/base with scores)
    champion = v0
    for v in versions:
        if v.scores and v.status in ("promoted", "base"):
            if v.generation > champion.generation or (
                v.generation == champion.generation and v.scores.aggregate > (champion.scores.aggregate if champion.scores else -1)
            ):
                champion = v

    # Figure out what generation was last completed
    max_completed_gen = 0
    generation_log: list[dict] = []

    # Gen 0 is done
    generation_log.append({
        "generation": 0,
        "champion_id": v0.id,
        "score": v0.scores.aggregate,
        "versions_tested": [v0.id],
        "mutation_target": None,
    })

    # Check each generation
    for gen in range(1, 100):
        vid_a = _version_id(run_id, gen, 0)
        vid_b = _version_id(run_id, gen, 1)
        a = version_map.get(vid_a)
        b = version_map.get(vid_b)

        if not a and not b:
            break

        a_scored = a and a.id in scored
        b_scored = b and b.id in scored

        if a_scored and b_scored:
            # Generation fully complete
            max_completed_gen = gen
            gen_versions = [v for v in [a, b] if v]
            winner = select_champion(champion, [v for v in gen_versions if v.scores])
            if winner:
                champion = winner
            generation_log.append({
                "generation": gen,
                "champion_id": champion.id,
                "score": champion.scores.aggregate,
                "versions_tested": [v.id for v in gen_versions],
                "mutation_target": a.mutation_target if a else None,
                "promoted": winner.id if winner else None,
            })
        else:
            # Partially complete — this is where we resume
            break

    all_version_ids = [v.id for v in versions]
    recent_scores = [entry["score"] for entry in generation_log]

    return {
        "found": True,
        "v0_scored": True,
        "champion": champion,
        "max_completed_gen": max_completed_gen,
        "generation_log": generation_log,
        "all_version_ids": all_version_ids,
        "recent_scores": recent_scores,
        "version_map": version_map,
        "scored": scored,
    }


async def run_evolution(
    max_generations: int = MAX_GENERATIONS,
    threshold: float = SCORE_THRESHOLD,
    conversations_per_persona: int = CONVERSATIONS_PER_PERSONA,
    on_progress: Callable[[dict], None] | None = None,
    resume_run_id: str | None = None,
    start_sections: dict[str, str] | None = None,
) -> AgentVersion:
    """Run the full evolution loop. Pass start_sections to evolve from champion instead of base."""

    def _progress(data: dict) -> None:
        if on_progress:
            on_progress(data)

    # --- RESUME or FRESH START ---
    start_gen = 1
    if resume_run_id:
        state = _rebuild_state_from_db(resume_run_id)
        if state.get("v0_scored"):
            run_id = resume_run_id
            champion = state["champion"]
            generation_log = state["generation_log"]
            all_version_ids = state["all_version_ids"]
            recent_scores = state["recent_scores"]
            start_gen = state["max_completed_gen"] + 1

            logger.info(f"=== RESUMING {run_id} from gen {start_gen} ===")
            logger.info(f"Current champion: {champion.id} (score: {champion.scores.aggregate:.2f})")
            _progress({
                "generation": start_gen - 1, "phase": "resumed",
                "message": f"Resumed from gen {start_gen - 1}, champion={champion.id}, score={champion.scores.aggregate:.2f}",
            })
        else:
            logger.warning(f"Cannot resume {resume_run_id} — v0 not scored. Starting fresh.")
            resume_run_id = None

    if not resume_run_id:
        run_id = f"run_{uuid4().hex[:8]}"
        generation_log = []
        all_version_ids = []
        recent_scores = []

        # --- INIT: Create and evaluate v0 ---
        if start_sections:
            logger.info(f"=== RUN {run_id}: Starting from champion prompt ===")
            _progress({"generation": 0, "phase": "init", "message": "Starting from champion prompt"})
            sections = start_sections
        else:
            logger.info(f"=== RUN {run_id}: Loading base prompt and creating v0 ===")
            _progress({"generation": 0, "phase": "init", "message": "Loading base prompt"})
            sections = load_base_prompt(BASE_PROMPT_PATH)
        v0_id = _version_id(run_id, 0)
        v0 = AgentVersion(
            id=v0_id,
            run_id=run_id,
            generation=0,
            prompt_sections=sections,
            status="base",
        )

        _progress({"generation": 0, "phase": "simulating", "message": "Running v0 simulations"})
        conversations = await run_full_evaluation_suite(v0, conversations_per_persona)
        for conv in conversations:
            save_conversation(conv)

        _progress({"generation": 0, "phase": "evaluating", "message": "Evaluating v0"})
        scores = await evaluate_all(conversations)
        v0.scores = scores
        save_version(v0)
        champion = v0
        all_version_ids.append(v0_id)
        recent_scores.append(scores.aggregate)

        generation_log.append({
            "generation": 0,
            "champion_id": v0_id,
            "score": scores.aggregate,
            "versions_tested": [v0_id],
            "mutation_target": None,
        })

        # Extract tactics from v0 conversations
        v0_tactics = await extract_tactics_from_conversations(conversations, v0_id, run_id)
        logger.info(f"v0: extracted {len(v0_tactics)} tactics")

        logger.info(f"v0 baseline score: {scores.aggregate:.2f}")
        _progress({"generation": 0, "phase": "done", "score": scores.aggregate, "tactics_extracted": len(v0_tactics)})

        # Save run immediately so it can be resumed
        _save_run(run_id, datetime.now(timezone.utc), champion, generation_log, all_version_ids, "in_progress")

        if scores.aggregate >= threshold:
            logger.info(f"v0 already meets threshold {threshold} — done!")
            _save_run(run_id, datetime.now(timezone.utc), champion, generation_log, all_version_ids, "threshold_reached")
            return champion

    run_start = datetime.now(timezone.utc)
    termination_reason = "max_generations"
    consecutive_same_section = 0
    last_section: str | None = None

    # --- EVOLUTION LOOP ---
    for gen in range(start_gen, max_generations + 1):
        logger.info(f"\n=== GENERATION {gen} ===")

        # 1. ANALYZE
        _progress({"generation": gen, "phase": "analyzing", "message": "Analyzing failures"})
        champion_convos = load_conversations(champion.id)
        patterns = await analyze_failures(champion_convos)

        if not patterns:
            logger.warning("No failure patterns found — stopping")
            termination_reason = "no_patterns"
            break

        # 2. SELECT TARGET
        target_pattern = patterns[0]
        target_section = target_pattern.target_section

        if target_section in IMMUTABLE_SECTIONS:
            target_pattern = patterns[1] if len(patterns) > 1 else patterns[0]
            target_section = target_pattern.target_section
            if target_section in IMMUTABLE_SECTIONS:
                logger.warning("All top patterns target immutable sections — stopping")
                termination_reason = "immutable_only"
                break

        if target_section == last_section:
            consecutive_same_section += 1
        else:
            consecutive_same_section = 0

        if consecutive_same_section >= 2:
            mutable = [s for s in PROMPT_SECTIONS if s not in IMMUTABLE_SECTIONS and s != target_section]
            if mutable:
                alt_patterns = [p for p in patterns if p.target_section in mutable]
                if alt_patterns:
                    target_pattern = alt_patterns[0]
                    target_section = target_pattern.target_section
                else:
                    target_section = mutable[0]
                    target_pattern.target_section = target_section
                logger.info(f"Forced diversification → targeting [{target_section}]")
                consecutive_same_section = 0

        last_section = target_section
        logger.info(f"Target section: [{target_section}] — {target_pattern.description}")

        # 3. MUTATE
        _progress({"generation": gen, "phase": "mutating", "message": f"Mutating [{target_section}]"})
        candidates_data = await generate_candidates(champion, target_pattern, num_candidates=2)

        # 4. SIMULATE + 5. EVALUATE candidates
        gen_version_ids: list[str] = []
        candidate_versions: list[AgentVersion] = []
        for idx, (rationale, section_name, new_sections) in enumerate(candidates_data):
            vid = _version_id(run_id, gen, idx)
            candidate = AgentVersion(
                id=vid,
                run_id=run_id,
                parent_id=champion.id,
                generation=gen,
                prompt_sections=new_sections,
                mutation_target=section_name,
                rationale=rationale,
                failure_patterns=[target_pattern.description],
                status="archived",
            )

            # Check if this candidate already has scores (partial resume)
            existing_convos = load_conversations(vid)
            if existing_convos and all(c.eval_result for c in existing_convos):
                logger.info(f"  {vid}: already evaluated, skipping simulation")
                _progress({"generation": gen, "phase": "skipped", "message": f"{vid} already scored"})
                candidate_scores = await evaluate_all(existing_convos)
                candidate.scores = candidate_scores
                save_version(candidate)
            else:
                _progress({"generation": gen, "phase": "simulating", "message": f"Simulating {vid}"})
                convos = await run_full_evaluation_suite(candidate, conversations_per_persona)
                for conv in convos:
                    save_conversation(conv)

                _progress({"generation": gen, "phase": "evaluating", "message": f"Evaluating {vid}"})
                candidate_scores = await evaluate_all(convos)
                candidate.scores = candidate_scores
                save_version(candidate)

            candidate_versions.append(candidate)
            gen_version_ids.append(vid)
            if vid not in all_version_ids:
                all_version_ids.append(vid)

            logger.info(f"  {vid}: aggregate={candidate_scores.aggregate:.2f}")

        # 5b. EXTRACT TACTICS from all candidate conversations
        gen_tactics_count = 0
        for cv in candidate_versions:
            cv_convos = load_conversations(cv.id)
            cv_tactics = await extract_tactics_from_conversations(cv_convos, cv.id, run_id)
            gen_tactics_count += len(cv_tactics)

        # 6. SELECT
        _progress({"generation": gen, "phase": "selecting", "message": "Selecting champion"})
        winner = select_champion(champion, candidate_versions)

        # 6b. RECORD FAILURES for non-promoted candidates
        gen_failures = record_failed_candidates(champion, candidate_versions, winner, run_id)

        if winner:
            winner.status = "promoted"
            save_version(winner)
            champion.status = "archived"
            save_version(champion)
            champion = winner
            logger.info(f"Promoted {winner.id} as new champion (score: {winner.scores.aggregate:.2f})")
        else:
            logger.info(f"No improvement — champion stays at {champion.id}")

        logger.info(f"Gen {gen}: {gen_tactics_count} tactics extracted, {len(gen_failures)} failures recorded")

        generation_log.append({
            "generation": gen,
            "champion_id": champion.id,
            "score": champion.scores.aggregate,
            "versions_tested": gen_version_ids,
            "mutation_target": target_section,
            "promoted": winner.id if winner else None,
            "tactics_extracted": gen_tactics_count,
            "failures_recorded": len(gen_failures),
        })

        _progress({
            "generation": gen, "phase": "done", "score": champion.scores.aggregate,
            "tactics_extracted": gen_tactics_count, "failures_recorded": len(gen_failures),
        })

        # Save progress after each generation so we can resume
        _save_run(run_id, run_start, champion, generation_log, all_version_ids, "in_progress")

        # 7. CHECK TERMINATION
        current_score = champion.scores.aggregate
        recent_scores.append(current_score)

        if current_score >= threshold:
            logger.info(f"Score {current_score:.2f} >= threshold {threshold} — evolution complete!")
            termination_reason = "threshold_reached"
            break

        if len(recent_scores) >= PLATEAU_WINDOW + 1:
            window = recent_scores[-(PLATEAU_WINDOW + 1):]
            improvement = window[-1] - window[0]
            if improvement < PLATEAU_EPSILON:
                logger.info(
                    f"Plateau detected: {improvement:.3f} improvement over "
                    f"{PLATEAU_WINDOW} generations — attempting diversification"
                )
                if consecutive_same_section == 0:
                    consecutive_same_section = 2
                else:
                    logger.info("Already diversified without progress — stopping")
                    termination_reason = "plateau"
                    break

    # --- POST-LOOP ---
    logger.info(f"\n=== EVOLUTION COMPLETE ===")
    logger.info(f"Champion: {champion.id} (generation {champion.generation})")
    logger.info(f"Final score: {champion.scores.aggregate:.2f}")

    from core.llm_client import usage
    logger.info(f"Token usage:\n{usage.summary()}")

    _save_run(run_id, run_start, champion, generation_log, all_version_ids, termination_reason)
    return champion


def _save_run(
    run_id: str,
    start_time: datetime,
    champion: AgentVersion,
    generation_log: list[dict],
    all_version_ids: list[str],
    termination_reason: str,
) -> None:
    """Persist evolution run metadata to MongoDB."""
    try:
        save_evolution_run({
            "id": run_id,
            "start_time": start_time.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "champion_id": champion.id,
            "generations_completed": len(generation_log) - 1,
            "final_score": champion.scores.aggregate if champion.scores else 0,
            "termination_reason": termination_reason,
            "generation_log": generation_log,
            "all_version_ids": all_version_ids,
        })
    except Exception:
        logger.warning("Failed to save evolution run metadata", exc_info=True)
