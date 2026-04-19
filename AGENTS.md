# AGENTS.md — Rules of Engagement

This document defines the mandatory workflow and technical standards for AI agents (Gemini, Claude, etc.) working on the `oatbrain` project. It is the operational counterpart to the [SPEC.md](SPEC.md). Adherence to these rules ensures architectural integrity and project safety.

## 1. Core Workflow: Research -> Strategy -> Execution

Every task MUST follow this lifecycle:

1.  **Research**: 
    - Validate assumptions using `grep_search`, `glob`, and `read_file`.
    - Map dependencies and understand existing patterns.
    - **Empirical Reproduction**: For bug fixes, you MUST reproduce the failure with a test case before applying the fix.
2.  **Strategy**: 
    - Summarize the intended changes concisely.
    - State the testing strategy for verification.
3.  **Execution (Plan -> Act -> Validate)**:
    - **Plan**: Detail the specific code changes and test cases.
    - **Act**: Apply surgical updates. Use ecosystem tools (like `ruff`, `mypy`) if available.
    - **Validate**: Run tests and linters. **Validation is the only path to finality.**

## 2. Architectural Mandates ([SPEC §23](SPEC.md#23-architecture))

- **Strict Separation**: `core/` MUST NOT import from `adapters/` or `ui/`. `adapters/` MUST NOT import from `ui/`.
- **Port-Driven**: All external interactions (IO, UI, Clock) MUST go through defined Protocols in `core/ports/`.
- **No Asyncio**: The project uses the GLib main loop. Do NOT introduce `asyncio` or `gbulb`. Use `ThreadPoolExecutor` and `GLib.idle_add` for background work ([SPEC §25](SPEC.md#25-concurrency--main-loop)).
- **Dependency Control**: Only use Debian-packaged libraries listed in [SPEC §2.2](SPEC.md#22-runtime-dependencies-debian-packages). No `pip install` at runtime.

## 3. Testing & Verification ([SPEC §30](SPEC.md#30-testing-strategy))

- **Universal Commands**: ALWAYS run validation via the `Makefile` using path-independent targets.
  - `make lint` — Ruff check and Mypy (system python3).
  - `make format` — Ruff formatting (system python3).
  - `make tach` — Architecture boundary check (via `.venv/bin/tach`).
  - `make test` — Run all unit tests (system python3).
- **Dependency Mandate**: ALL dependencies installable via Debian MUST be used via the system-packaged versions. Only `tach` is permitted in a virtual environment.
- **Coverage Floor**: Maintain at least 50% overall coverage. New features MUST include unit tests for core logic.
- **Fast First**: Prioritize unit tests over GUI/Smoke tests during development.
- **No App Start**: Do NOT call `app.run()` or start the full application loop during automated tests. Validation should focus on unit logic and widget hierarchy without requiring a running application process. Manual verification of the UI is the responsibility of the user unless explicitly requested otherwise.
- **Fakes over Mocks**: Prefer `tests/fakes/` (in-memory implementations) over `unittest.mock` ([SPEC §30.3](SPEC.md#303-fakes-vs-mocks)).
- **Architecture Linting**: Run `make tach` to ensure boundary integrity. NEVER run `tach` directly; always use the make target or `.venv/bin/tach`.


## 4. Operational Safety

- **Git Discipline**: Never stage or commit changes unless explicitly requested.
- **Reliable PR Creation**: To avoid shell syntax errors (e.g. from backticks or brackets in Markdown) and interactive prompts:
  1. ALWAYS push the branch first using `git push -u origin <branch-name>`.
  2. ALWAYS write the PR body to a temporary file (e.g., `/tmp/pr_body.md`).
  3. Create the PR using `gh pr create --title "..." --body-file /tmp/pr_body.md`.
- **Credential Protection**: Never log, print, or commit API keys or secrets. Check `.env` and `.gitignore`.
- **Context Efficiency**: Combine tool calls where possible. Read only what is necessary.
- **Explain Before Acting**: Provide a concise one-sentence explanation of intent before executing tools.
- **Preserve Shell Script Permissions**: Never write to `run.sh` or any `.sh` file using the Write tool — it strips the executable bit. If a shell script must be modified, use the Edit tool only. If a git operation or checkout causes the executable bit to be lost, immediately restore it with `chmod +x`.

## 5. UI & Styling ([SPEC §20](SPEC.md#20-themes--styling))

- **Libadwaita**: Use standard Adw widgets. Follow system accent and light/dark preferences.
- **Theme Tokens**: All styling MUST use CSS custom properties defined by the theme engine.

## 6. Documentation & Tracking Synchronization

- **Source of Truth**: GitHub Projects and Issues are the primary tools for tracking progress and task status.
- **Sync Mandate**: When a meaningful change to requirements or architecture is requested by the user, you MUST:
    1. Update [SPEC.md](SPEC.md) to reflect the new truth.
    2. Update relevant GitHub issues or create new ones using the `gh` tool.
    3. Update [PLAN.md](PLAN.md) to ensure it remains in sync with the GitHub project board and issue state.

## 7. Specialized Skills & Command Triggers

The following skills are available in the workspace to streamline the PR-driven workflow. Agents MUST activate these skills when triggered by the user.

| Skill | Activation Trigger | Purpose |
| :--- | :--- | :--- |
| `oatbrain-pr-step` | "Proceed to next step" | Implements next `PLAN.md` item, creates branch/PR, validates CI. |
| `oatbrain-pr-reviewer` | "Check PR feedback", "Address PR comments" | Summarizes/addresses review comments on GitHub. |

---
*Note: This document is a living contract. Update it as the project's architectural patterns evolve.*
