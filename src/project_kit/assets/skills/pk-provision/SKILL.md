---
name: pk-provision
description: Create the milestones, labels, branches, GitHub Project and issues of the approved backlog in the repository's provider (phase 5). Use when the user wants to publish the plan to GitHub or to sync new backlog entries.
---

# pk-provision — phase 5

Turn `.project-kit/backlog.json` into real milestones, labels, branches, a Project and issues.
This writes to the provider, so nothing happens without the user's explicit consent.

## Before starting

- The plan must be approved: `project-kit approve plan` (the pk-plan skill does it).
- Run `project-kit doctor`. `gh` must be logged in with the `repo` and `project` scopes.
- The repository must already have a commit on its main branch.

## Steps

1. Run `project-kit provision --dry-run` and show the user the plan it prints: what will be
   created, what already exists, and the note about branch protection.
   - A `BLOCKING` line means nothing can be applied; explain it and help fix it.
2. Ask the user whether to go ahead. Only after an explicit "yes" run
   `project-kit provision --yes`. Never pass `--yes` without that consent.
3. Report the result. Running the command again is always safe: it only creates what is
   missing, never rewrites existing issues and never moves cards the user has moved.

## Things to tell the user

- Project **views** (Board, Roadmap, table) cannot be created through the API; they are made by
  hand once in the Project's page.
- Branch protection is only reported, never configured. On a private repository with a free
  plan GitHub does not offer it; the branch rules are then followed by discipline.
- If GitHub says the rate limit was reached, wait a minute and run the command again: the
  progress is saved and the command resumes where it stopped.

## Rules

- Do not edit `.project-kit/state.json`; project-kit owns it.
- To add work later, edit the backlog (pk-plan), validate it and run this again.
