# project-kit

[![PyPI](https://img.shields.io/pypi/v/project-kit-cli)](https://pypi.org/project/project-kit-cli/)
[![License: MIT](https://img.shields.io/pypi/l/project-kit-cli)](https://github.com/miguelmatg/project-kit/blob/main/LICENSE)

**Everything that happens before the first line of code.** project-kit guides you, with an AI
agent, through defining a project, deciding its stack and architecture, agreeing how the team
works and planning the backlog. It then sets up GitHub and hands the project over to
[Spec Kit](https://github.com/github/spec-kit), which specifies and builds each feature.

```
idea ──▶ brief ──▶ decisions (ADRs) ──▶ workflow ──▶ backlog ──▶ GitHub ──▶ Spec Kit
         /pk-discover   /pk-decide       /pk-workflow   /pk-plan   /pk-provision  /pk-handoff
```

The conversations run in your AI agent (today, [Claude Code](https://claude.com/claude-code)) as
`/pk-…` skills: one question at a time, a recommended answer for each, and everything written to
documents in your repository. Every phase ends with your approval, and every document can be
written by hand instead.

> **Status: alpha.** It works end to end on GitHub with Claude Code. GitLab and other agents are
> planned.

## Requirements

- [uv](https://docs.astral.sh/uv/) (it also fetches Python 3.12+ if you do not have it)
- `git`
- [Claude Code](https://claude.com/claude-code), to run the guided phases
- [`gh`](https://cli.github.com/), logged in with the `repo` and `project` scopes
  (`gh auth login`, then `gh auth refresh -s project`), to create things on GitHub

`project-kit doctor` checks all of this for you. Spec Kit is installed for you at the end, if
you want it.

## Install

```bash
uv tool install project-kit-cli      # installs the `project-kit` command
uv tool upgrade project-kit-cli      # later, to update the program
```

The package is called `project-kit-cli`; the command is `project-kit`. To try it without
installing: `uvx --from project-kit-cli project-kit help`.

**Updating a project.** `init` copies the skills and templates into your repository and never
overwrites them, so a new version of the program does not change a project that already exists.
Run `project-kit upgrade` inside it to see what is out of date, and `project-kit upgrade --apply`
to bring it up to date. Files you edited are never overwritten; see
[upgrading](https://github.com/miguelmatg/project-kit/blob/main/docs/upgrade.md).

## Quick start

In your repository, new or existing:

```bash
cd my-project
project-kit init
```

`init` copies the skills and templates into the repository and then offers to open Claude Code
right there, already running `/pk-start` (press Enter to accept). `/pk-start` asks whether to
**only initialise** or to **start defining the project now**, and after every phase it asks
whether to continue or stop. You can leave at any point and come back later:

```bash
project-kit status     # where you are and what comes next
project-kit help       # a visual guide to the flow and the commands
```

## The phases

| # | Skill | What it does | Produces |
|---|---|---|---|
| 0 | `/pk-start` | Checks your setup and lets you choose: only initialise, or start now | `.project-kit/` |
| 1 | `/pk-discover` | Interviews you about the project: problem, users, scope, constraints | `docs/project/brief.md` |
| 2 | `/pk-decide` | Guides the technical decisions: monolith or monorepo, language, package manager, data, auth, hosting | `docs/adr/*.md` |
| 3 | `/pk-workflow` | Agrees how the team works: branches, reviews, quality gates | `docs/development-workflow.md` |
| 4 | `/pk-plan` | Derives phases, epics and a backlog from all of the above | `docs/project/roadmap.md`, `.project-kit/backlog.json` |
| 5 | `/pk-provision` | Creates milestones, labels, branches, the GitHub Project and the issues | GitHub |
| 6 | `/pk-handoff` | Prepares the Spec Kit constitution; each issue becomes a spec | `.project-kit/handoff/constitution-input.md` |

Each phase ends with an explicit approval (`project-kit approve <phase>`), and a phase cannot be
approved while an earlier one is still open. The phases are listed in `.project-kit/workflow.yml`;
for a small project, switch one off with `enabled: false`.

To fill a document by hand instead, copy the matching template from `.project-kit/templates/`
(`brief.md`, `adr.md`, `development-workflow.md`). The skills read what is already there and only
ask about what is missing.

## Existing repositories and Projects

`init` never overwrites a file, so it is safe in a repository that already has code, documents or
a `.claude/` folder. Before creating a GitHub Project, `provision` looks at the ones already
linked to the repository: with one it asks whether to use it, with several it lists them, and
with none it asks for a name. Use `--project <number or title>` to choose without being asked.
It never rewrites issues that already exist, and re-running it is always safe.

## Commands

| Command | What it does |
|---|---|
| `project-kit init` | Install the skills, templates and workflow in the current directory |
| `project-kit status` | Show the phases and what comes next |
| `project-kit upgrade [--apply] [--adopt] [--diff]` | Update the skills and templates a project already has |
| `project-kit help` | Show a visual guide (also what plain `project-kit` prints) |
| `project-kit doctor` | Check that git, gh, uv and Spec Kit are available |
| `project-kit approve <phase>` | Record your sign-off of a phase |
| `project-kit backlog validate` | Validate `.project-kit/backlog.json` |
| `project-kit provision [--dry-run] [--project X]` | Create milestones, branches, the Project and issues on GitHub |
| `project-kit handoff [--install-speckit]` | Generate the Spec Kit constitution input |

Useful `init` options: `--project-name`, `--language` (language of the generated documents),
`--agent claude|none` (open the agent or not) and `--ai-coauthor keep|remove`.

## AI co-author

`init` asks whether AI assistants may appear as co-authors of your commits and pull requests. If
not, it configures Claude Code to stop signing them and installs a `commit-msg` hook that strips
the co-author trailer of other assistants. Switch the hook on once per clone with
`git config core.hooksPath .githooks`.

## After the handoff

`/pk-handoff` leaves a text file for Spec Kit's constitution and tells you the next step:

```
/speckit-constitution @.project-kit/handoff/constitution-input.md
```

From there Spec Kit does the work. Each issue of the backlog is one spec: its text is the input of
`/speckit-specify`, followed by `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks` and
`/speckit-implement`. project-kit never writes inside `.specify/` and does not write specs.

The constitution is generated from your own rules: the branch pattern and merge strategy you agreed,
the decisions on record, and an index of where each kind of rule lives (including the GitHub
Project used for tasks). Once the constitution is written, `project-kit approve handoff` deletes
the temporary input files; from then on the constitution is the single source.

## What it adds to your repository

```
.project-kit/          config.yml, state.json, workflow.yml, templates/, handoff/
.claude/skills/pk-*/   the skills
docs/project/          brief.md, roadmap.md        (created by the phases)
docs/adr/              one file per decision       (created by the phases)
.githooks/commit-msg   only if you removed the AI co-author
```

## Documentation

More detail lives in the repository (in Spanish):
[design](https://github.com/miguelmatg/project-kit/blob/main/docs/design.md),
[backlog schema](https://github.com/miguelmatg/project-kit/blob/main/docs/backlog-schema.md),
[provisioning](https://github.com/miguelmatg/project-kit/blob/main/docs/provisioning.md) and
[Spec Kit handoff](https://github.com/miguelmatg/project-kit/blob/main/docs/handoff.md).

## Feedback

Ideas and bug reports are welcome as
[issues](https://github.com/miguelmatg/project-kit/issues). Pull requests are not accepted; see
[CONTRIBUTING](https://github.com/miguelmatg/project-kit/blob/main/CONTRIBUTING.md).

## License

[MIT](https://github.com/miguelmatg/project-kit/blob/main/LICENSE)
