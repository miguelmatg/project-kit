---
name: pk-workflow
description: Agree how the team will work (branches, pull requests, reviews, commits, versioning, quality gates, definition of done) and write docs/development-workflow.md. Use when the user wants to define the development process or change it.
---

# pk-workflow — phase 3

Record **how the project is developed**: the process that the plan, the provisioned
repository and the Spec Kit constitution will all follow. It is written in
`docs/development-workflow.md` (template: `.project-kit/templates/development-workflow.md`),
by this interview or by hand.

Read `.project-kit/templates/interview.md` first and follow it.

## Inputs

- `docs/project/brief.md` and `docs/adr/*.md`: team size, repository structure, package
  manager and CI already decided there are not asked again; link them.
- `.project-kit/config.yml`: branch names (`main`, `release`, `develop`) and provider.
- The PR and issue templates that `project-kit init` put in `.project-kit/templates/github/`.

## Topics (maximum 8 questions; propose a default for each and ask only what matters)

- **Team and review:** how many people, who approves, how many approvals.
- **Branches:** keep `main` / `release` / `develop` with one branch per spec, or a lighter
  model (only `main`) for a small project. Name the types of working branch.
- **Merging:** merge strategy per branch, who may merge, tags and releases.
- **Commits and versions:** commit convention, versioning scheme.
- **Repository tooling:** formatters, linters, git hooks, which follow from the ADRs.
- **Quality gates:** what must be green before merging (tests, lint, types, security scan).
- **Definition of Done.**
- **Git hosting rules:** branch protection availability on the hosting plan.

## Steps

1. Create `docs/development-workflow.md` from the template if it does not exist; fill in what
   the ADRs and config already settle.
2. Interview on the rest, then write the answers into the document after each one.
3. **Record what was agreed as data** in `.project-kit/config.yml`: the handoff generates the
   Spec Kit constitution from these values, not from the prose of the document, so they must
   say the same thing as the document:

   ```yaml
   branches:            # the three permanent branches (three different names)
     main: main
     release: release
     develop: develop
   workflow:
     spec_branch: "spec/<name>"   # how the branch of one spec is named
     merge:                       # how pull requests are merged into each branch
       develop: squash            # squash | merge | rebase
       release: merge
       main: merge
   ```

   If the user changes branch names or drops `release`/`develop`, edit `branches:` too. Tell
   the user what you wrote.
4. **Present** the document and the open markers; offer a clarification pass.
5. **Approval gate.** On an explicit choice of "Approve it", set `**Status**: Approved` and
   run `project-kit approve workflow`.
6. Run `project-kit status` and offer `pk-plan` next: continue now, or stop here.

## Rules

- Do not configure anything in the provider here: branches and protection are created by
  `pk-provision`, after the plan.
- Do not repeat technical decisions; link the ADR.
- The document and the `workflow:` / `branches:` values of `config.yml` must never disagree.
  If the user changes one later, change the other.
- Write in the language of `config.yml`.
