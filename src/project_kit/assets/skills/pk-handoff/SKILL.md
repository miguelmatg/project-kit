---
name: pk-handoff
description: Hand the project over to Spec Kit: generate the constitution input from the project's decisions and set up Spec Kit (phase 6). Use when planning and provisioning are done and the user wants to start specifying features.
---

# pk-handoff — phase 6

Prepare the text for `/speckit-constitution`, make sure Spec Kit is available, and point the
user at the first specs. Spec Kit owns `.specify/`; project-kit never writes inside it.

## Steps

1. Ask, with a selection list (`AskUserQuestion`: **No extra rules** / **Yes, I have some**),
   whether the project has rules of its own that should be part of the constitution
   (security, compliance, performance, team conventions). If yes, collect them and write them
   as a Markdown list to `.project-kit/handoff/constitution-extra.md`; they are added under
   "Project-specific rules". Governance content only: no feature requests, no implementation
   tasks. Everything else the constitution needs (principles, the branch pattern and merge
   strategy from `config.yml`, the decisions on record, and an index of where each kind of rule
   lives, including the GitHub Project used for tasks) is generated for you.
2. Run `project-kit handoff --dry-run` and show the user what will be generated.
3. Run `project-kit handoff`. It writes `.project-kit/handoff/constitution-input.md` and
   reports the state of Spec Kit.
4. If Spec Kit is not ready, explain what `project-kit handoff --install-speckit` would run
   (it installs the `specify-cli` package with `uv` and runs `specify init --here`, which
   merges Spec Kit's files into the repository). Only after an explicit choice to go ahead,
   run `project-kit handoff --install-speckit --yes`.
5. Tell the user to run, in this session:
   `/speckit-constitution @.project-kit/handoff/constitution-input.md`
   You cannot run that command for them.
6. When the constitution is written, read `.specify/memory/constitution.md` and check that it
   kept what the input said: the branch pattern and the merge strategy of `config.yml`, the
   section "Where the project's rules live" (or its content) and the reference to the GitHub
   Project for tasks. If something is missing, tell the user and suggest amending it with
   `/speckit-constitution` before continuing.
7. Suggest mentioning `docs/project/`, `docs/adr/` and `docs/development-workflow.md` in
   `CLAUDE.md` or `AGENTS.md`. Explain that from here Spec Kit does the work: each backlog
   issue is one spec, and its text (description and acceptance criteria) is the input of
   `/speckit-specify`; then `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks` and
   `/speckit-implement`. project-kit does not write specs. Suggest the order: the issues of
   the first phase, by priority.
8. When the user confirms the constitution is in place, run `project-kit approve handoff`. It
   refuses while `.specify/memory/constitution.md` is missing or still Spec Kit's template, and
   when it succeeds it **deletes** `constitution-input.md` and `constitution-extra.md`: they
   only exist to feed `/speckit-constitution`, and from then on the constitution is the one
   source. Tell the user they were removed.

## Rules

- `constitution-input.md` is regenerated every time until the handoff is approved. Do not edit
  it; put project-specific rules in `constitution-extra.md`. If the user removes its
  `project-kit:managed` header the file is theirs and is no longer regenerated.
- Both files are temporary. After the handoff, rules change by amending the constitution with
  `/speckit-constitution`, not by recreating them.
- Never modify anything inside `.specify/` by hand.
- If project-kit warns about an untested Spec Kit version, tell the user, but continue: the
  only thing project-kit depends on is the input file.
