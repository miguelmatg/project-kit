---
name: pk-init
description: Check requirements and set up project-kit in the current repository (phase 0). Use when the user wants to start defining a new project with project-kit, or asks to check that their tools are ready.
---

# pk-init — phase 0

Prepare the repository for project-kit. Nothing is created in GitHub in this phase.

## Steps

1. Run `project-kit doctor`.
   - `FAIL` lines are blocking: explain each hint to the user and wait until they are fixed.
   - `warn` lines are optional (`uv` and Spec Kit are only needed at the handoff phase).
2. If `.project-kit/config.yml` does not exist, ask the user for:
   - the project name,
   - the provider (`github` today, `gitlab` later),
   - the language for the generated documents.

   Then run `project-kit init --here --project-name <name> --provider <provider> --language <language>`.
3. Read `.project-kit/config.yml` back to the user and ask them to confirm it. Branch names
   (`main`, `release`, `develop`) can be edited by hand.
4. Tell the user which phases come next. Only the phases whose skills are installed in
   `.claude/skills/` can be run.

## Rules

- `project-kit init` never overwrites existing files, so it is safe to run again.
- Do not edit `.project-kit/state.json` by hand; project-kit owns it.
