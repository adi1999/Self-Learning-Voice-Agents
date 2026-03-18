---
name: coding-discipline
description: Enforces modular, disciplined coding practices. Use on EVERY code task — writing new code, editing existing files, refactoring, debugging, or building features. Triggers on any request involving code creation or modification.
---

# Coding Discipline

## Before Writing ANY Code

### 1. Understand First
Do NOT start writing code immediately. Before touching anything:
- Read the relevant files/modules involved
- Understand the current architecture and data flow
- Identify what already exists that can be reused

### 2. Cross-Check Before Writing New
Before creating any new function, class, or module:
- Search the codebase for existing implementations that do the same or similar thing
- If something close exists, extend or refactor it — don't duplicate
- Ask yourself: "Does this already exist somewhere?" If unsure, check.

## Core Rules

### Modular Code
- Every function does ONE thing
- If a function is doing two things, split it
- Name functions by what they do, not how they do it
- Keep coupling between modules low — pass data, not dependencies

### Meaningful Changes Only
When modifying existing code:
- Understand WHY the current code is written the way it is before changing it
- Consider downstream impact — what else depends on this?
- Don't refactor adjacent code unless asked to — stay focused on the task
- If a change seems risky, flag it before making it

### Utils Pattern
Move all deterministic, pure functions to utils:
- Data transformations, formatters, validators, parsers → utils
- When adding a util, add a one-line comment: what it does + where it's used
- Example:
```python
# Converts flat product list to category-grouped dict. Used in: template_recommender, landing_page_builder
def group_by_category(products: list) -> dict:
```
- If a helper is used in only one place, keep it local. The moment it's used in two places, move it to utils.

### File Size: Hard Limit < 400 Lines
This is a hard restriction. No file should exceed 400 lines. Period.
- If a file is approaching 400 lines, split it before it gets there
- Split by responsibility, not arbitrarily — each resulting file should have a clear purpose
- When splitting: update all imports, verify nothing breaks
- If you're editing a file already over 400 lines, flag it and propose a split plan before making changes

## When Presenting Code

Always briefly state:
- **Where**: Which file(s) are being created/modified
- **What**: What the code does (one sentence)
- **Why**: Why this approach (only if non-obvious)

Do not dump code without context.

## Checklist (Run Mentally Before Every Code Block)
1. Did I check if this already exists?
2. Is this function doing only one thing?
3. Is this deterministic logic that belongs in utils?
4. Will this file stay under 400 lines?
5. Did I state where this goes and what it does?
