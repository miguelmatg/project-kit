---
name: pk-handoff
description: Hand the project over to Spec Kit: generate the constitution input from the project's decisions and set up Spec Kit (phase 6). Use when planning and provisioning are done and the user wants to start specifying features.
---

# pk-handoff — phase 6

Prepare the text for `/speckit-constitution`, make sure Spec Kit is available, and point the
user at the first specs. Spec Kit owns `.specify/`; project-kit never writes inside it.

## Steps

1. Ask the user whether the project has rules of its own that should be part of the
   constitution (security, compliance, performance, team conventions). If so, write them as
   a Markdown list to `.project-kit/handoff/constitution-extra.md`. That file is yours and
   project-kit never overwrites it; it is added under "Project-specific rules".
   Governance content only: no feature requests, no implementation tasks.
2. Run `project-kit handoff --dry-run` and show the user what will be generated.
3. Run `project-kit handoff`. It writes `.project-kit/handoff/constitution-input.md` and
   reports the state of Spec Kit.
4. If Spec Kit is not ready, explain what `project-kit handoff --install-speckit` would run
   (it installs the `specify-cli` package with `uv` and runs `specify init --here`, which
   merges Spec Kit's files into the repository). Only after an explicit "yes", run
   `project-kit handoff --install-speckit --yes`.
5. Tell the user to run, in this session:
   `/speckit-constitution @.project-kit/handoff/constitution-input.md`
   You cannot run that command for them.
6. After the constitution exists, suggest mentioning `docs/project/` and `docs/adr/` in
   `CLAUDE.md` or `AGENTS.md`, and explain that each backlog issue is a candidate spec: its
   text is the input of `/speckit-specify`.
7. When the user confirms the constitution is in place, run `project-kit approve handoff`.

## Rules

- `constitution-input.md` is regenerated every time. Do not edit it; put project-specific rules
  in `constitution-extra.md`. If the user removes its `project-kit:managed` header the file is
  theirs and is no longer regenerated.
- Never modify anything inside `.specify/` by hand.
- If project-kit warns about an untested Spec Kit version, tell the user, but continue: the
  only thing project-kit depends on is the input file.
