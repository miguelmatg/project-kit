---
name: pk-decide
description: Guide the user through the technical and architectural decisions of the project (repository structure, language, framework, package manager, data, auth, hosting, CI) and record each one as an ADR in docs/adr/. Use when the user wants to choose the stack or architecture, or to revisit a decision.
---

# pk-decide — phase 2

Turn the brief into **decisions**: one ADR per decision, with the options considered and the
reason for the choice. project-kit does not choose for the user; it makes the choice
explicit, argued and written down. The ADRs feed the plan and, later, the Spec Kit
constitution.

Read `.project-kit/templates/interview.md` first and follow it. ADRs use
`.project-kit/templates/adr.md`, are named `docs/adr/NNNN-short-title.md` (next free number)
and can also be written by hand.

## Inputs

- `docs/project/brief.md`, especially "Constraints" and "Technical preferences already
  stated". Preferences are proposals to confirm, not decisions.
- Existing `docs/adr/*.md`: never decide twice. To change a decision, write a new ADR and mark
  the old one `Superseded by ADR-NNNN`.

## Steps

1. **List the decisions this project needs**, from this checklist and from the brief; leave
   out whatever does not apply (a command-line tool has no auth or hosting question):
   - Repository: single repository, monorepo or several repositories; monolith or separate
     services.
   - Language and runtime; framework(s).
   - Package manager and, for monorepos, workspace and build tooling (for example pnpm, npm,
     yarn, uv, cargo workspaces, turborepo, nx).
   - Data: storage, migrations, backups.
   - Authentication and authorisation.
   - API style and integrations with external services.
   - Hosting, environments and deployment; CI.
   - Testing approach and tools; observability.
   - Anything the brief marks as legal or compliance-driven.
2. **Show the list** and ask which ones are *critical* now (they block planning) and which
   can wait. In "light" mode, only decide the critical ones. Deferred decisions are written
   as `Status: Proposed` or left for a later `pk-decide`.
3. **For each decision, one at a time:**
   1. Ask the question in the interview format: options with pros and cons for *this*
      project, a recommendation with the reason, and what depends on the answer. Use the
      brief's constraints (team skills, budget, scale, compliance) as the drivers.
   2. If a decision follows from an earlier one (a framework implies a language), do not ask:
      state it and record it in the ADR as a consequence.
   3. After the answer, write the ADR immediately (`Status: Accepted`, today's date) and tell
      the user its path.
4. **Check consistency** across ADRs: no contradictory choices (for example a package manager
   that the chosen framework does not support). Raise any conflict as a question.
5. **Present** the list of ADRs with their status and anything still undecided.
6. **Approval gate.** When the critical ADRs are accepted and the user explicitly approves,
   run `project-kit approve decide`.
7. Run `project-kit status` and offer `pk-workflow` next: continue now, or stop here.

## Rules

- Do not decide on the user's behalf and do not present your recommendation as settled.
- Never invent versions, prices or benchmarks; if a fact matters and you are not sure, say so
  and mark it `[NEEDS CLARIFICATION]`.
- Keep each ADR to one decision. Write them in the language of `config.yml`.
- The `Status:` line matters: the handoff reads it to build the constitution.
