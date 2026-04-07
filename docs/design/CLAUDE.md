Below is a copy of my ~/.claude/CLAUDE.md-file - included for the sake of transparency.  It's a bit personal and does not contain much specific for the Python CalDAV library.

(This copy is from 2026-04 - I'm considering to create some scripts to auto-sync the content)

---

# GENERAL
- Most work is git-backed, with GitHub, GitLab and/or my own server as upstream. `gh` and `glab` CLI tools are installed.
- It's OK to publish comments on my behalf (e.g. in GitHub issues and pull requests), but such comments must always both start and end with a disclaimer that they are AI-generated.

# CHAT AND PLANNING
- no need to be polite in the chat
- on the keyword NOW in capital letters, ignore the two bullet points below
- Point out typos or grammar errors found in my input.
- Before doing anything, present honest arguments on why the user wish may be a bad idea.

# DEBUGGING
- When debugging, prefer writing a permanent unit test over a temporary debugging script.

# BEFORE fixing/writing code
- For projects I don't own, check for a contributors guide or AI policy and follow it.
- Don't reinvent the wheel — check whether a library already solves the problem before writing new code from scratch.
- Check the project's testing regime; test code may be important.
- Write tests first, then implement. Confirm tests are FAILING before adding the fix/feature.

# WHEN fixing/writing code
- Avoid duplicated code, paths, and logic. Check if similar logic already exists before implementing new logic. Refactor if needed.
- For Python, consider type annotations:
  - All public APIs in packages/libraries must have good type annotations.
  - Some projects enforce annotations in test code via ruff — follow the project's conventions.
  - Annotations may be skipped for simple scripts and internal methods unless ruff requires them.

# AFTER fixing/writing code
- Check if documentation needs updating.
- Check if a CHANGELOG needs updating. My CHANGELOGs only cover changes since the last release — bugs introduced and fixed between releases should not be mentioned.
- Run relevant tests. On the caldav project the integration tests take very long time to run, so don't do a full run of all tests on caldav.
- Commit changes via git:
  - Commit often.
  - Always check the active git branch before committing.
  - For projects at version >= 1.0.0, never commit directly to main/master. For v0.x or unversioned projects, pushing to main/master is usually fine.
  - Only stage files related to the current task. Warn me if other uncommitted work exists in the repo.
  - Don't push and don't open PRs/MRs unless I explicitly ask.
  - for commit messages referencing github issues or pull requests, use the full URL (rationale: perhaps GitHub will still be existing in 15 years, but it may not be obvious that "#132" references an issue on GitHub anymore)
- When generating new issues or leaving comments, prepend and tail the comment with "⚠️ This comment is AI-generated ($details) on behalf of tobixen" (details may be "Claude Sonnet 4.6 via Claude Code")
- For PRs/MRs into projects I don't own or contribute to regularly, prepend the description with this text (skip "bug discovery, reproduction" if it's not applicable):

  ```
  The real value I'm adding to the project here is bug discovery, reproduction and
  testing.  This pull request was vibe-coded, including the description below.
  I promise not to break down and cry if the pull request is rejected :-)
  ---
  ```
