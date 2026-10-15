<!-- Shared by pk-discover, pk-decide and pk-workflow. Same technique as Spec Kit's clarify. -->
# How project-kit interviews

Every guided phase follows these rules. Edit this file to change the style of the questions
for the whole project.

## Before asking anything

1. Read `.project-kit/config.yml`: write everything in its `language`.
2. Read the document the phase produces if it already exists. The user may have filled it in
   by hand or in an earlier session. Only ask about what is **Missing** or **Partial**; never
   ask again what the document already answers.
3. Read the documents of the earlier phases: they are the context, not something to ask again.
4. Build, internally, a list of the topics of the phase marked Clear / Partial / Missing. Do
   not show it unless there is nothing left to ask.
5. Keep the questions that change what gets built or decided, ordered by impact times
   uncertainty. Drop trivia and anything that belongs to a later phase.

## Asking

- **One question at a time.** Never reveal the questions that are still queued. Two or three
  questions that clearly do not depend on each other may go together in one call.
- **Use the agent's selection list, not typed letters.** In Claude Code, ask with the
  `AskUserQuestion` tool whenever the answer is one of a few options: the user then picks from
  a list with the arrow keys instead of typing. Fill it like this:
  - `question`: a full question that ends in `?` and makes sense on its own (no topic labels as
    questions), followed by one plain sentence saying what depends on the answer.
  - `header`: one or two words naming the topic (12 characters at most).
  - `options`: 2 to 4 mutually exclusive choices, each with a short `label` (one to five words)
    and a `description` with the pros, cons and consequences **for this project**.
  - Put your recommendation **first** and end its label with `(Recommended)`; say why in its
    description. Do not add an "Other" option: the tool already offers one for a typed answer.
  - Use `multiSelect: true` only when several options can be true at once (for example which
    integrations are needed).
  - When options need a side-by-side look (two configurations, two structures), put it in each
    option's `preview`.
  - More than four real alternatives: offer the three or four that fit best, and say the rest
    are reachable through "Other".
- **Plain text only where a list does not fit:** an open question with no discrete options (a
  name, a number, a description). Ask it in a sentence with a suggested answer when you have
  one: `**Suggested:** <answer> - <reason>`, and accept "yes" as agreement. The same format,
  with the options as a table and `**Recommended:** Option B - <reason>`, is the fallback when
  the agent has no selection tool.
- If an answer is ambiguous, ask a quick follow-up. It does not count as a new question.
- Stop when the topics that matter are Clear, when the user says "done", "enough" or "skip",
  or when you reach the question limit of the phase. Unanswered topics stay in the document
  as `[NEEDS CLARIFICATION: <question>]`.

## Recording

- **Save the document after each accepted answer**, not at the end, so nothing is lost if the
  session stops.
- Put each answer in the section where it belongs, replacing the text it makes obsolete
  instead of adding contradictions. Keep each statement short and verifiable.
- Log it too, under `## Clarifications` > `### Session YYYY-MM-DD`, as
  `- Q: <question> -> A: <answer>`.
- Where the user left a choice open, make an informed guess from the context, write it down
  under **Assumptions** and say so. Use `[NEEDS CLARIFICATION: ...]` only when the choice
  changes the scope or has no reasonable default, with a maximum of three at the end of a
  pass.
- Never invent facts about the user's business, users or constraints.

## Finishing

1. Tell the user what was written and which markers remain open.
2. Ask with a selection list (`AskUserQuestion`): **Approve it**, **Look for gaps first** (a
   clarification pass of at most 5 more questions), or **I want changes** (the user says what).
3. Approval gate: only an explicit choice of "Approve it" in this conversation allows running
   `project-kit approve <phase>`. Never approve on the user's behalf, and never because an
   earlier question was answered.
4. After approving, run `project-kit status` and ask, again with a list, whether to **Continue
   with the next phase** now or **Stop here** and come back later with its skill. Respect the
   answer.
