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

- **One question at a time.** Never reveal the questions that are still queued.
- Start the line with `**Question:**` and make it a full question that ends in `?` and makes
  sense on its own (no topic labels as questions). Follow it with one plain sentence,
  `Why it matters:`, saying what depends on the answer.
- When there are discrete options (2 to 5, mutually exclusive), say which one you recommend
  and why, then list all of them:

  `**Recommended:** Option B - <one or two sentences of reasoning for this project>`

  | Option | Description |
  |--------|-------------|
  | A | ... |
  | B | ... |
  | Other | Your own answer |

  Close with: `Reply with a letter, say "yes" to take the recommendation, or write your own
  answer.`
- When there are no discrete options, offer a suggested answer instead:
  `**Suggested:** <answer> - <reason>`, and accept "yes" or "suggested" as agreement.
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
2. Offer a clarification pass: "Do you want me to look for gaps and ask a few more
   questions, or is this good enough to approve?" A pass asks at most 5 more questions.
3. Approval gate: ask explicitly whether the document is approved. Only an explicit "yes" in
   this conversation allows running `project-kit approve <phase>`. Never approve on the
   user's behalf, and never because an earlier question was answered.
4. After approving, run `project-kit status` and offer the next phase: continue now, or
   stop here and come back later with its skill. Respect the answer.
