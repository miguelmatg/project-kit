---
name: pk-discover
description: Interview the user about what the project is (problem, users, scope, constraints, success criteria) and write docs/project/brief.md; also clarifies an existing brief. Use when the user wants to define or describe the project, refine the brief, or after pk-start.
---

# pk-discover — phase 1

Produce the **project brief**: what the project is and why, not how it is built. Technology is
decided in the next phase (`pk-decide`). The brief can be written by this interview, filled
in by hand from `.project-kit/templates/brief.md`, or both.

Read `.project-kit/templates/interview.md` first and follow it: one question at a time with a
recommended answer, save after every answer, mark gaps, approval only on an explicit "yes".

## Inputs

- `.project-kit/config.yml` (name, language) and `project-kit status`.
- The description the user gave in `pk-start`, if any.
- `docs/project/brief.md`, if it exists (hand-written or from an earlier session): ask only
  about what is missing or partial.

## Steps

1. If `docs/project/brief.md` does not exist, create it from `.project-kit/templates/brief.md`
   (replace `{{project_name}}`), and fill in whatever the user's description already answers.
2. **Scan the brief** against these topics, marking each Clear / Partial / Missing:
   - Problem and value: who hurts, how, what happens today without it.
   - Users and stakeholders: roles, how they differ, who decides.
   - Scope: the capabilities that must exist, grouped by theme, and what is explicitly out.
   - Success criteria: how the user will know it worked, measurable where possible.
   - Constraints: legal and compliance, budget, deadline, team size and skills, existing
     systems, data residency.
   - Data and integrations: what information is handled, which external services are needed.
   - Risks and assumptions: what could make the project fail, what is being taken for granted.
   - Terminology: words with an ambiguous meaning in this domain.
3. **Interview** on the Partial and Missing topics, highest impact first, with a maximum of
   **8 questions** in the first pass. Keep them at product level: if the user volunteers a
   technology ("it will be in Next.js", "we use pnpm"), do not debate it; write it under
   "Technical preferences already stated" for `pk-decide` and move on.
4. If the user gave nothing to start from, begin with: "In a few sentences, what do you want
   to build and who is it for?" and derive the next questions from the answer.
5. **Check quality** before presenting: every goal and success criterion is verifiable, the
   scope has an "out of scope" list, no statement names a technology as a requirement.
6. **Present** a short summary of the brief and the markers still open.
7. **Offer a clarification pass** (at most 5 more questions) before approval.
8. **Approval gate.** When the user explicitly approves, set `**Status**: Approved` in the
   brief and run `project-kit approve discover`.
9. Run `project-kit status` and offer `pk-decide` next: continue now, or stop here.

## Rules

- Never invent users, numbers, deadlines or constraints. Unknown means a
  `[NEEDS CLARIFICATION: ...]` marker or a labelled assumption.
- Write the brief in the language of `config.yml`.
- Do not run `project-kit approve discover` without an explicit "yes".
- The brief is the user's document: if they edit it by hand between questions, re-read it
  before the next change.
