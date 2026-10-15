---
name: pk-plan
description: Turn the project's brief and decisions into a phased roadmap and a validated backlog (.project-kit/backlog.json). Use when the user wants to plan the project, break it into phases and epics, or revise the backlog before provisioning.
---

# pk-plan — phase 4

Produce the project backlog and get it approved. Nothing is created in the provider here;
that happens later, in the provision phase.

## Inputs

- `docs/project/brief.md` (scope, goals, constraints), `docs/adr/*.md` (decisions) and
  `docs/development-workflow.md` (process). The plan is **derived** from them: scope becomes
  epics, constraints and decisions become issues (repository setup, CI, the chosen
  infrastructure) in the first phase.
- **Run `project-kit status` first.** If an enabled earlier phase is not done, stop and tell
  the user which skill to run (`/pk-discover`, `/pk-decide`, `/pk-workflow`). Do not
  improvise a brief. If they want to skip a phase, they set `enabled: false` on it in
  `.project-kit/workflow.yml`; only then plan without it, and say what is missing.
- `.project-kit/config.yml` (project name, language, provider).
- `.project-kit/templates/backlog.example.json`: follow its shape exactly.

Write the backlog content in the language set in `config.yml`.

## Steps

1. **Draft the phases.** Each phase becomes a milestone and a value of the Phase field.
   Keep them few and ordered by delivery (for example `v0.1 MVP`, `v0.2`, `v1.0`).
2. **Draft the epics**, one per coherent delivery inside a phase.
3. **Break each epic into issues** (`feature`, `bug`, `chore`, `adr`, `docs`) with `parent`
   pointing at the epic. Give every `feature`, `bug` and `chore` concrete acceptance
   criteria: observable statements a reviewer can tick, not tasks.
4. **Set priority (P0–P3) and size (XS–XL)** on every issue. Prefer small issues; split
   anything you would size XL unless it is an epic.
5. **Write the file** to `.project-kit/backlog.json`.
6. **Validate:** run `project-kit backlog validate`. Fix every problem it reports and run it
   again until it passes. Never hand-edit your way around a validation error.
7. **Present the plan** to the user: the summary printed by the validator plus, per phase, the
   epics and their issues in a short list.
8. **Approval gate.** Ask the user explicitly whether the plan is approved. If they ask for
   changes, edit the backlog, validate again and present it again. Only when they say yes,
   run `project-kit approve plan`.
9. Optionally write `docs/project/roadmap.md` summarising the phases and epics for humans.
10. Run `project-kit status` and offer `pk-provision` next: continue now, or stop here.

## Rules

- Do not run `project-kit approve plan` without an explicit "yes" from the user in this
  conversation, and never approve on their behalf.
- Ids are lowercase words joined by hyphens and stay stable once provisioned; do not rename
  them when revising a backlog that was already provisioned.
- Do not edit `.project-kit/state.json` by hand.
- Each issue is meant to become a Spec Kit spec later: keep it about one deliverable, with
  acceptance criteria a reviewer can verify.
