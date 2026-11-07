# Working with me

Goal: get the task right using as few tokens as possible. These rules are
short on purpose: this file is loaded into every session.

## Before starting
- Name the deliverable in one sentence before the first edit: the file(s)
  you'll change, the PR title, or the command output you expect. If you can't
  name it, ask me one short question instead of exploring.
- Ask first only when a wrong guess means real rework. Otherwise pick the
  obvious option, say which one, and go.

## Research, then edit
- Search before reading: grep/glob for the symbol or text, then read only the
  matching section with a line range. Don't read whole files or folders
  "for context". Unfocused reading is the biggest token cost.
- Always read a file before editing it, but don't re-read a file you just
  edited to check it. The edit tool already confirms the change.
- Before changing a function's behavior or signature, grep for every caller
  and update them in the same change, so nothing breaks later.
- When I point at a spot ("file X lines 40-80, the foo function"), read only
  that range plus what it directly calls.

## Keep tool output small
- Trim noisy output: `| head`, `-q`/`--quiet`, `tail -n 50` for logs,
  `git diff --stat` before a full diff. Every printed line costs tokens.
- Run the narrowest check that proves the change (one test file or test
  name), not the whole suite, unless the change touches many places.
- Run independent commands together in one step.
- Don't start subagents unless I ask: they start from zero and cost more.

## When something fails
- Work from the real error output, not guesses.
- If the same approach fails twice, stop. Never try a third time on one fix:
  tell me what you tried, the exact error, and your best next idea.
- If you go about 10 minutes (or many tool calls) without an edit, stop and
  check with me.

## Long sessions
- If the session gets long or goes in circles, restate the working context
  in under 10 bullets (goal, relevant files, failing command/output,
  constraints), drop the dead ends, and continue from that.
- After editing CLAUDE.md, settings or MCP config, tell me to start a new
  session: those only load when a session starts.
- Remind me to stay on one model per session (switching mid-task re-reads
  everything).

## Replies
- Short. Lead with the result. No recap of my request, no restating the plan
  after doing it, no summary of things that didn't change.
- Show only the code that changed, never whole files.
