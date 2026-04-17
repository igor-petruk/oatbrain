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

- **Coverage Floor**: Maintain at least 50% overall coverage. New features MUST include unit tests for core logic.
- **Fast First**: Prioritize unit tests over GUI/Smoke tests during development.
- **Fakes over Mocks**: Prefer `tests/fakes/` (in-memory implementations) over `unittest.mock` ([SPEC §30.3](SPEC.md#303-fakes-vs-mocks)).
- **Architecture Linting**: Run `tach check` (or the equivalent import check) to ensure boundary integrity.

## 4. Operational Safety

- **Git Discipline**: Never stage or commit changes unless explicitly requested.
- **Credential Protection**: Never log, print, or commit API keys or secrets. Check `.env` and `.gitignore`.
- **Context Efficiency**: Combine tool calls where possible. Read only what is necessary.
- **Explain Before Acting**: Provide a concise one-sentence explanation of intent before executing tools.

## 5. UI & Styling ([SPEC §20](SPEC.md#20-themes--styling))

- **Libadwaita**: Use standard Adw widgets. Follow system accent and light/dark preferences.
- **Theme Tokens**: All styling MUST use CSS custom properties defined by the theme engine.

---
*Note: This document is a living contract. Update it as the project's architectural patterns evolve.*
