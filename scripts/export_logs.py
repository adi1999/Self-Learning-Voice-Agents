"""Export human-readable logs for assignment submission.

Generates:
  data/logs/version_archive.md    — all versions with scores, lineage, status
  data/logs/evaluation_scores.md  — per-version, per-persona score breakdowns
  data/logs/prompt_changes.md     — before/after prompt diffs for each mutation
  data/logs/evolution_runs.md     — run summaries with generation-by-generation logs
  data/logs/playbook.md           — accumulated tactics and failed approaches
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import PROJECT_ROOT
from core.archive import get_evolution_runs, list_versions, load_conversations, load_version
from core.db import strategy_tactics_collection, failed_approaches_collection
from core.prompt_builder import load_base_prompt
from config.settings import BASE_PROMPT_PATH

LOGS_DIR = PROJECT_ROOT / "data" / "logs"


def export_version_archive() -> None:
    """Version archive with scores and lineage."""
    versions = list_versions()
    lines = ["# Version Archive\n"]
    lines.append(f"Total: {len(versions)} versions\n")
    lines.append("| ID | Gen | Status | Parent | Mutation Target | Aggregate Score | Run |")
    lines.append("|---|---|---|---|---|---|---|")

    for v in versions:
        score = f"{v.scores.aggregate:.2f}" if v.scores else "N/A"
        parent = v.parent_id or "—"
        target = v.mutation_target or "—"
        run = v.run_id or "—"
        lines.append(f"| `{v.id}` | {v.generation} | {v.status} | `{parent}` | {target} | {score} | `{run}` |")

    (LOGS_DIR / "version_archive.md").write_text("\n".join(lines))
    print(f"  version_archive.md — {len(versions)} versions")


def export_evaluation_scores() -> None:
    """Per-version, per-persona score breakdowns."""
    versions = list_versions()
    lines = ["# Evaluation Scores\n"]

    for v in sorted(versions, key=lambda x: (x.run_id or "", x.generation)):
        if not v.scores:
            continue
        lines.append(f"## {v.id} (Gen {v.generation}, {v.status})")
        lines.append(f"**Aggregate: {v.scores.aggregate:.2f}**\n")

        if v.rationale:
            lines.append(f"*Rationale: {v.rationale}*\n")

        lines.append("| Persona | Goal (0-3) | Quality (1-5) | Compliance (0/1) | Consistency (0/1) | Sentiment (-1 to 1) | Weighted Total |")
        lines.append("|---|---|---|---|---|---|---|")
        for persona, ms in v.scores.per_persona.items():
            lines.append(
                f"| {persona} | {ms.goal_completion:.2f} | {ms.conversational_quality:.2f} | "
                f"{ms.compliance:.1f} | {ms.response_consistency:.1f} | "
                f"{ms.sentiment_shift:.2f} | **{ms.weighted_total:.2f}** |"
            )
        lines.append("")

    (LOGS_DIR / "evaluation_scores.md").write_text("\n".join(lines))
    scored = sum(1 for v in versions if v.scores)
    print(f"  evaluation_scores.md — {scored} scored versions")


def export_prompt_changes() -> None:
    """Before/after prompt diffs for each mutation."""
    versions = list_versions()
    base_sections = load_base_prompt(BASE_PROMPT_PATH)

    lines = ["# Prompt Changes\n"]
    lines.append("Each mutation rewrites one section of the prompt. Compliance is immutable.\n")

    # Base prompt first
    lines.append("## Base Prompt (v0)\n")
    for section in ["identity", "objective", "compliance", "opening", "strategy", "closing"]:
        lines.append(f"### {section.upper()}\n```\n{base_sections[section].strip()}\n```\n")

    # Mutations
    mutated = [v for v in versions if v.mutation_target and v.parent_id]
    mutated.sort(key=lambda x: (x.run_id or "", x.generation))

    for v in mutated:
        try:
            parent = load_version(v.parent_id)
        except ValueError:
            continue

        section = v.mutation_target
        parent_text = parent.prompt_sections.get(section, "").strip()
        new_text = v.prompt_sections.get(section, "").strip()

        if parent_text == new_text:
            continue

        score_before = f"{parent.scores.aggregate:.2f}" if parent.scores else "N/A"
        score_after = f"{v.scores.aggregate:.2f}" if v.scores else "N/A"

        lines.append(f"---\n## {v.id} (Gen {v.generation}) — mutated `{section}`")
        lines.append(f"**Score: {score_before} → {score_after}** | Status: {v.status} | Run: `{v.run_id}`\n")

        if v.rationale:
            lines.append(f"**Rationale:** {v.rationale}\n")

        lines.append(f"### BEFORE ({parent.id})\n```\n{parent_text}\n```\n")
        lines.append(f"### AFTER ({v.id})\n```\n{new_text}\n```\n")

    (LOGS_DIR / "prompt_changes.md").write_text("\n".join(lines))
    print(f"  prompt_changes.md — {len(mutated)} mutations")


def export_evolution_runs() -> None:
    """Run summaries with generation-by-generation logs."""
    runs = get_evolution_runs()
    lines = ["# Evolution Runs\n"]
    lines.append(f"Total: {len(runs)} runs\n")

    for run in runs:
        lines.append(f"## {run['id']}")
        lines.append(f"- **Final score:** {run.get('final_score', 'N/A')}")
        lines.append(f"- **Generations:** {run.get('generations_completed', 'N/A')}")
        lines.append(f"- **Termination:** {run.get('termination_reason', 'N/A')}")
        lines.append(f"- **Champion:** `{run.get('champion_id', 'N/A')}`")
        lines.append(f"- **Start:** {run.get('start_time', 'N/A')}")
        lines.append(f"- **End:** {run.get('end_time', 'N/A')}\n")

        gen_log = run.get("generation_log", [])
        if gen_log:
            lines.append("| Gen | Champion | Score | Mutation Target | Promoted |")
            lines.append("|---|---|---|---|---|")
            for g in gen_log:
                promoted = g.get("promoted") or "—"
                target = g.get("mutation_target") or "—"
                lines.append(
                    f"| {g['generation']} | `{g['champion_id']}` | {g['score']:.2f} | {target} | `{promoted}` |"
                )
        lines.append("")

    (LOGS_DIR / "evolution_runs.md").write_text("\n".join(lines))
    print(f"  evolution_runs.md — {len(runs)} runs")


def export_playbook() -> None:
    """Accumulated tactics and failed approaches."""
    tactics = list(strategy_tactics_collection.find({}, {"_id": 0}).sort("score_impact", -1))
    failures = list(failed_approaches_collection.find({}, {"_id": 0}).sort("created_at", -1))

    lines = ["# Strategy Playbook\n"]
    lines.append(f"**{len(tactics)} tactics** extracted, **{len(failures)} failed approaches** recorded.\n")

    lines.append("## Winning Tactics\n")
    lines.append("| # | Persona | Section | Score | Tactic |")
    lines.append("|---|---|---|---|---|")
    for i, t in enumerate(tactics, 1):
        lines.append(
            f"| {i} | {t['persona_type']} | {t['prompt_section']} | {t['score_impact']:.2f} | {t['tactic']} |"
        )

    lines.append("\n## Failed Approaches\n")
    lines.append("| # | Section | Reason | Score Delta | Description |")
    lines.append("|---|---|---|---|---|")
    for i, f in enumerate(failures, 1):
        delta = f"{f['score_before']:.2f} → {f['score_after']:.2f}"
        lines.append(
            f"| {i} | {f['target_section']} | {f['failure_reason']} | {delta} | {f['description'][:150]} |"
        )

    (LOGS_DIR / "playbook.md").write_text("\n".join(lines))
    print(f"  playbook.md — {len(tactics)} tactics, {len(failures)} failures")


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Exporting logs to {LOGS_DIR}/\n")
    export_version_archive()
    export_evaluation_scores()
    export_prompt_changes()
    export_evolution_runs()
    export_playbook()
    print(f"\nDone. Files in {LOGS_DIR}/")


if __name__ == "__main__":
    main()
