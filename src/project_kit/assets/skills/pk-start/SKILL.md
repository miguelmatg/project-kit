---
name: pk-start
description: Start here. Check that project-kit is ready in this repository, settle the basics (language, AI co-author policy) and ask whether to only initialise or to start defining the project right away. Use when the user has just run `project-kit init`, wants to begin a new project, or asks where to start.
---

# pk-start — phase 0

Entry point of project-kit. The files are already in the repository (`project-kit init` put
them there); this skill checks them, settles the basics and lets the user choose how far to go
now. Nothing is created in GitHub or GitLab here.

## Steps

1. **Check the tools.** Run `project-kit doctor`.
   - `FAIL` lines block: explain each hint and wait until it is fixed.
   - `warn` lines are optional (`uv` and Spec Kit are only needed at the handoff phase).
2. **Read the setup.** If `.project-kit/config.yml` is missing, tell the user to run
   `project-kit init` in the terminal and stop. Otherwise read it back (project name,
   provider, language, branches) and ask with a selection list (`AskUserQuestion`: **It is
   right** / **Change something**) whether it is right. These are plain values that can
   also be edited by hand. If the language is wrong, edit `language:` in the file.
3. **AI co-author.** If `config.yml` says `ai_coauthor: true` and the user has not been
   asked yet, ask with a selection list (**Keep them as co-authors** / **Remove them**) whether
   AI assistants (Claude, Copilot...) should appear as co-authors of commits and pull
   requests. If they do not want it:
   - set `ai_coauthor: false` in `config.yml` and run `project-kit init`: it makes Claude
     Code stop signing (`attribution` in `.claude/settings.json`) and installs a
     `commit-msg` hook that strips the co-author trailer of any other assistant;
   - ask before running `git config core.hooksPath .githooks`, which switches the hook on for
     this clone. Each teammate runs that command once.
4. **Ask how far to go now**, with a selection list (`AskUserQuestion`, see
   `.project-kit/templates/interview.md`) and exactly these two options. Put B first with
   `(Recommended)` unless the user said they are in a hurry:

   | Option | What happens |
   |--------|--------------|
   | **B. Start defining the project** | Continue now with the discovery interview |
   | **A. Only initialise** | Stop here. The user comes back later with `/pk-discover` |
5. **If A:** run `project-kit status`, show it, and explain that `/pk-discover` is next. Done.
6. **If B:** ask for a short description of the project in the user's own words, a few
   sentences, a pasted note or "nothing yet, ask me". Then follow the `pk-discover` skill
   (`.claude/skills/pk-discover/SKILL.md`) using that description as the starting point.

## Rules

- `project-kit init` never overwrites existing files, so it is safe to run again.
- Do not edit `.project-kit/state.json` by hand; project-kit owns it.
- The phases are listed in `.project-kit/workflow.yml`; the user may disable some of them
  (`enabled: false`) for a small project. `project-kit status` shows what is left.
