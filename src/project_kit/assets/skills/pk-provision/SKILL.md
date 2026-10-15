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

1. Run `project-kit provision --dry-run`. You have no terminal for the command's own
   questions, so it never asks: it uses the only Project it finds, or stops and tells you what
   to choose. Show the user the plan it prints: what will be created, what already exists, and
   the note about branch protection.
   - A `BLOCKING` line means nothing can be applied; explain it and help fix it.
   - The `Project:` line says which GitHub Project will be used: one already linked to the
     repository (`already exists`) or a new one. Ask which one they want with a selection
     list (`AskUserQuestion`, see `.project-kit/templates/interview.md`): the detected
     Project (Recommended), another existing one, or a new one (then ask its name). Whatever
     they choose, run the dry run again with `--project "<number or exact title>"` (a new
     title creates it), so the plan matches. The choice is remembered afterwards.
   - If it stops with "Several Projects match this repository" or "There is no terminal to
     ask which GitHub Project to use", offer the listed Projects (up to three, plus "Other"
     for a new name) in a selection list and rerun with `--project`.
2. Ask with a selection list whether to go ahead (**Create it all** / **Not yet**). Only after
   the first run `project-kit provision --yes` (with the same `--project`). Never pass `--yes`
   without that consent.
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
