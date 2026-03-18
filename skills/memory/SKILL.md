---
name: memory
description: Maintain AI memory files in .claude/memory/. Use when saving learnings, cleaning up stale memory, resolving teammate conflicts, or organizing project knowledge. Works for both Claude Code and Cursor.
---

# Memory Management

Shared project memory lives in `.claude/memory/` and is **committed to git**. Both Claude Code and Cursor read from here. Multiple teammates contribute, so conflict resolution matters.

## Memory Location

```
.claude/
├── memory/
│   ├── MEMORY.md          ← Index file (loaded every session, keep under 200 lines)
│   ├── architecture.md    ← System design, product structure, key integrations
│   ├── conventions.md     ← Code patterns, naming, file organization standards
│   ├── debugging.md       ← Solutions to recurring problems, gotchas
│   └── {topic}.md         ← Additional topic files as needed
```

**MEMORY.md** is the entry point. It should be a concise index with summaries and pointers to topic files. Only the first 200 lines are loaded into Claude Code's context per session — everything after is truncated.

## What to Remember

**Save:**
- Stable patterns confirmed across multiple sessions (e.g., "always use `poetry run` for backend commands")
- Architectural decisions with rationale (e.g., "chat moved under construction_proposal because frontend already organized it that way")
- Key file paths and project structure that's hard to rediscover
- Debugging solutions that took significant effort to find
- User/team preferences for workflow, tools, communication style
- Integration details (API endpoints, config vars, external service quirks)

**Don't save:**
- Session-specific context (current task, in-progress work, temp state)
- Information already in CLAUDE.md (don't duplicate — CLAUDE.md is for rules, memory is for knowledge)
- Speculative conclusions from reading a single file
- Anything obvious from the code itself (e.g., "the User model is in models.py")

## When to Update

**Add** when you discover something that would save time in a future session.

**Update** when facts change — a refactor moves files, an API prefix changes, a convention evolves. Don't leave stale information.

**Remove** when content is outdated, wrong, or duplicated elsewhere. Stale memory is worse than no memory — it actively misleads.

**Don't touch** when the information is still accurate and useful. Not every session needs a memory update.

## How to Organize

### MEMORY.md (the index)

Keep it structured by topic with brief summaries. Link to topic files for details.

```markdown
# Project Memory

## Architecture
- Multi-product backend: `app/products/{product}/` — see architecture.md
- Chat uses RAGFlow + OpenAI streaming — see architecture.md#chat

## Conventions
- API prefix pattern: `/api/{product}/{feature}/...` — see conventions.md
- Frontend hooks use raw fetch, not generated client — see conventions.md#frontend

## Debugging
- RAGFlow connection issues — see debugging.md#ragflow
```

### Topic files

One file per broad topic. Use headings within the file, not one file per factoid. A file should be 50-500 lines. If it exceeds 500, split by subtopic.

### Naming

Use lowercase, descriptive names: `architecture.md`, `debugging.md`, `conventions.md`, `ragflow-integration.md`. No dates in filenames — memory is living documentation, not a changelog.

## Conflict Resolution

Since memory is committed to git, teammates will sometimes edit the same files. When you encounter a merge conflict or contradictory information:

### Git merge conflicts

1. **Read both sides** of the conflict fully before resolving
2. **Combine knowledge** — memory is additive. If teammate A added a debugging tip and teammate B updated architecture notes in the same file, keep both
3. **Don't pick sides blindly** — if two entries genuinely contradict (e.g., "always use X" vs "never use X"), flag it in the file with a `TODO: resolve` marker and mention it to the user
4. **Preserve the more recent fact** when one entry is simply an update to stale information (e.g., "API prefix is /api/chat" vs "API prefix is /api/construction-proposal/chat" — the latter wins because it reflects a migration)

### Detecting stale/conflicting content (no git conflict)

Sometimes memories contradict without a git merge conflict — a teammate updated code but didn't update memory, or two topic files say different things.

When you notice this:
1. Check which version matches the actual code (code is the source of truth)
2. Update the memory to match reality
3. If you can't verify, add a `<!-- needs-review -->` comment and mention it to the user

### Prevention

- Keep memory entries small and focused — smaller entries mean fewer conflicts
- Reference file paths and code patterns rather than duplicating code (code changes, memory won't auto-update)
- When making big refactors, update memory in the same commit

## Cross-Tool Usage

This memory is read by both **Claude Code** and **Cursor**.

- **Claude Code**: Automatically loads MEMORY.md (first 200 lines) every session via the auto-memory system. Topic files are read on demand.
- **Cursor**: Needs to be told to read from `.claude/memory/`. Add this to `.cursorrules`:
  ```
  Project memory is stored in .claude/memory/MEMORY.md and related topic files.
  Read MEMORY.md at the start of any task to understand project context, conventions, and known issues.
  ```

Both tools use the same memory files. When either tool updates memory, the changes are available to the other on next session (after git pull).

## Routine Maintenance

Do this periodically (every few weeks or after major refactors):

1. **Scan for staleness** — Read through MEMORY.md and topic files. Does everything still match the actual code? Remove or update anything outdated.
2. **Check for bloat** — Is MEMORY.md over 200 lines? Move details to topic files, keep only summaries in the index.
3. **Look for duplication** — Is anything in memory also word-for-word in CLAUDE.md or skills? Remove from memory (CLAUDE.md and skills are the authoritative sources for rules and workflows).
4. **Verify cross-references** — Do file paths mentioned in memory still exist? Update any that moved.
