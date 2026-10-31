---
name: agno-cursor-unit-tests
description: >-
  Runs agno-cursor-agent unit tests in the project venv via Composer subagents.
  Use when implementing features, fixing bugs, or before claiming tests pass;
  launches a test-weakening verifier then a dedicated unit-test runner (Composer 2.5).
---

# agno-cursor-agent unit tests

## When to use

- After changing `src/`, `tests/`, or `pyproject.toml`
- Before telling the user that unit tests pass
- When the user asks to run tests

## Orchestration (parent agent)

Run **two steps in order**. Use `Task` with `subagent_type: generalPurpose` and **`model: composer-2.5-fast`** for both.

### Step 1 — Test weakening verifier

**Goal:** Detect whether test changes cheat (weaker assertions, deleted coverage, skipped tests, looser mocks, lowered thresholds).

**Isolation (required):** The verifier prompt must contain **only**:

1. The fixed role block below (verbatim).
2. A unified diff of test files — nothing else.

Do **not** include: user messages, feature descriptions, implementation plans, product intent, or non-test diffs. Generate the diff yourself in the parent shell, then paste **only** that diff into the verifier prompt.

**Diff commands (pick one):**

```bash
# Uncommitted + staged test changes
git diff HEAD -- tests/ pyproject.toml

# Branch vs main (PR-style)
git diff origin/main...HEAD -- tests/ pyproject.toml
```

**Verifier prompt template:**

```text
You are a test-integrity verifier. You receive ONLY a unified diff of test-related files.

Find evidence of weakened tests: removed or softened assertions, deleted tests without equivalent replacement, added skip/xfail to hide failures, broadened mocks, commented-out expectations, or lowered coverage thresholds in pyproject.toml.

Do not infer author intent. Do not use any context outside the diff.

Reply with exactly one JSON object (no markdown fences):
{"verdict":"clean"|"weakened","findings":[{"file":"...","summary":"..."}]}
```

If `verdict` is `weakened`, **stop** and report findings to the user. The **parent agent** decides whether each finding is acceptable (expected behavior change) or must be reverted/fixed. Do not run Step 2 until the parent accepts or fixes.

If there is **no diff** under `tests/` or test config in `pyproject.toml`, skip Step 1 and note "no test diff to verify."

### Step 2 — Unit test runner

Launch only after Step 1 is `clean` or skipped.

**Runner prompt template:**

```text
Run unit tests for agno-cursor-agent at: <absolute repo root>

From that directory, execute:
  chmod +x scripts/run-unit-tests.sh
  ./scripts/run-unit-tests.sh

Do not use Conda base python or PYTHONPATH-only hacks.

Return: exit code, pass/fail summary, and the last ~40 lines of output if failed.
```

## Parent agent decisions after verification

| Verifier result | Action |
|-----------------|--------|
| `clean` | Proceed to Step 2 |
| `weakened` | Present findings; user/parent decides fix vs accept |
| Runner failed | Fix code or tests; re-run from Step 1 if tests changed |

## Local one-liner (humans or parent shell)

```bash
./scripts/run-unit-tests.sh
```
