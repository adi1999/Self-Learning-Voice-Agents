"""Story landing page endpoint: single-call aggregation of evolution data."""

from fastapi import APIRouter

from core.archive import load_version
from core.db import (
    agent_versions_collection,
    conversations_collection,
    evolution_runs_collection,
)
from core.playbook import get_playbook_stats, get_top_tactics

router = APIRouter(prefix="/api/story", tags=["story"])


@router.get("/")
def get_story():
    """Return all data needed for the Story landing page in one call."""

    # Get ALL runs sorted by score
    all_run_docs = list(evolution_runs_collection.find().sort("final_score", -1))
    if not all_run_docs:
        return {"run": None}

    # Best run for the main story
    run_doc = all_run_docs[0]
    run_doc.pop("_id", None)
    run_id = run_doc["id"]

    # All runs summary
    all_runs = []
    for rd in all_run_docs:
        rd.pop("_id", None)
        all_runs.append({
            "id": rd["id"],
            "generations_completed": rd.get("generations_completed", 0),
            "final_score": rd.get("final_score", 0.0),
            "termination_reason": rd.get("termination_reason", "unknown"),
            "champion_id": rd.get("champion_id", ""),
        })

    # --- Run summary ---
    generation_log = run_doc.get("generation_log", [])
    run_summary = {
        "id": run_id,
        "generations_completed": run_doc.get("generations_completed", 0),
        "final_score": run_doc.get("final_score", 0.0),
        "termination_reason": run_doc.get("termination_reason", "unknown"),
        "generation_log": [
            {
                "generation": entry.get("generation", 0),
                "champion_id": entry.get("champion_id", ""),
                "score": entry.get("score", 0.0),
                "mutation_target": entry.get("mutation_target"),
                "promoted": entry.get("promoted"),
            }
            for entry in generation_log
        ],
    }

    # --- v0 and champion versions ---
    v0_id = generation_log[0]["champion_id"] if generation_log else "v0"
    champion_id = run_doc.get("champion_id", v0_id)

    try:
        v0_version = load_version(v0_id)
    except ValueError:
        v0_version = None

    try:
        champion_version = load_version(champion_id)
    except ValueError:
        champion_version = None

    def _build_version_summary(version, include_mutation=False, include_prompt=False):
        if not version or not version.scores:
            return None
        per_persona = {
            persona: round(ms.weighted_total, 2)
            for persona, ms in version.scores.per_persona.items()
        }
        result = {
            "id": version.id,
            "score": version.scores.aggregate,
            "per_persona": per_persona,
        }
        if include_mutation:
            result["mutation_target"] = version.mutation_target
            result["rationale"] = version.rationale
        if include_prompt:
            result["prompt_sections"] = version.prompt_sections
        return result

    v0_summary = _build_version_summary(v0_version)
    champion_summary = _build_version_summary(
        champion_version, include_mutation=True, include_prompt=True
    )

    # --- Biggest improvement (by delta) ---
    biggest_improvement = None
    weakest_v0_persona = None
    if v0_summary and champion_summary:
        best_delta = -999.0
        best_persona = None
        worst_score = 999.0
        worst_persona = None
        for persona, before_score in v0_summary["per_persona"].items():
            after_score = champion_summary["per_persona"].get(persona, before_score)
            delta = after_score - before_score
            if delta > best_delta:
                best_delta = delta
                best_persona = persona
            if before_score < worst_score:
                worst_score = before_score
                worst_persona = persona

        if best_persona is not None:
            biggest_improvement = {
                "persona": best_persona,
                "before": v0_summary["per_persona"][best_persona],
                "after": champion_summary["per_persona"].get(
                    best_persona, v0_summary["per_persona"][best_persona]
                ),
                "delta": round(best_delta, 3),
            }
        if worst_persona is not None:
            weakest_v0_persona = {
                "persona": worst_persona,
                "score": round(worst_score, 2),
            }

    # --- Top tactics ---
    tactics = get_top_tactics(limit=5)
    top_tactics = [
        {
            "persona_type": t.persona_type,
            "prompt_section": t.prompt_section,
            "tactic": t.tactic,
            "score_impact": t.score_impact,
        }
        for t in tactics
    ]

    # --- Playbook stats ---
    stats = get_playbook_stats()
    playbook_stats = {
        "total_tactics": stats["total_tactics"],
        "total_failures": stats["total_failures"],
    }

    # --- Totals ---
    total_conversations = conversations_collection.count_documents({})
    total_versions = agent_versions_collection.count_documents({})

    return {
        "run": run_summary,
        "all_runs": all_runs,
        "v0": v0_summary,
        "champion": champion_summary,
        "biggest_improvement": biggest_improvement,
        "weakest_v0_persona": weakest_v0_persona,
        "top_tactics": top_tactics,
        "playbook_stats": playbook_stats,
        "total_conversations": total_conversations,
        "total_versions": total_versions,
    }
