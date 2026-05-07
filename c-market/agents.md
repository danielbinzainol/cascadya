# AGENTS.md file

# Dev tips
- Format all edited Python files with ruff format
- Always run Python tooling with explicit venv executables:
  - .\.venv\Scripts\python.exe -m pytest ...
  - .\.venv\Scripts\ruff.exe format ...
  - .\.venv\Scripts\uv.exe ...

  ## Reuse-First Policy (Very Important)

- Prefer reusing existing code over creating new functions/classes.
- Before adding any new function, search for relevant existing utilities/clients and use them when possible.
- In priority order:
  1. Reuse existing domain clients/services.
  2. Reuse existing helper functions.
  3. Create new code only if reuse is clearly not possible.

- If multiple valid implementations exist (reuse vs new abstraction), pause and ask for confirmation before coding.
- In your response, explicitly state:
  - what existing code was found,
  - what was reused,
  - and why any new function was necessary.
