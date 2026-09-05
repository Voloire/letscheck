# Cerchi Idee? Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic “Cerchi Idee?” multi-object DSO planner using the local catalog and balcony constraints.

**Architecture:** A pure catalog-profile layer classifies candidates; a vectorized/coarse astronomy layer produces visibility intervals; a pure planner selects non-overlapping blocks with a two-hour minimum; a dedicated local API and small UI card expose the plan. Existing single-target `/api/check` behavior remains unchanged.

**Tech Stack:** Python 3, SQLite, Astropy, stdlib HTTP server, vanilla HTML/CSS/JS, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-05-cerchi-idee-design.md`

## Global Constraints

- Keep execution local and deterministic; no network and no LLM.
- Minimum continuous block per object: 2 hours (7200 seconds).
- Future search limit: 90 days.
- Preserve existing single-target validation and UI.
- Do not add AI attribution or alter Git identity.

---

### Task 1: Candidate profile rules

**Files:**
- Create: `astrochecker/idea_profiles.py`
- Test: `tests/test_idea_profiles.py`

- [ ] **Step 1: Write failing tests** for all clusters eligible, emission/reflection priority, beginner boost, compact-galaxy rule, and exclusions.
- [ ] **Step 2: Run `pytest tests/test_idea_profiles.py -q` and confirm the expected failures.
- [ ] **Step 3: Implement pure `classify_candidate(record) -> dict` and `IDEA_MIN_BLOCK_SECONDS = 7200`.
- [ ] **Step 4: Run the focused tests and confirm green.

### Task 2: Catalog candidate query

**Files:**
- Modify: `astrochecker/catalog.py`
- Test: `tests/test_catalog.py`

- [ ] **Step 1: Add a failing acceptance test for `Catalog.idea_candidates()` returning classified records with coordinates, aliases, type, and profile metadata.
- [ ] **Step 2: Run the focused test and confirm failure.
- [ ] **Step 3: Add the read-only query and deterministic ordering.
- [ ] **Step 4: Rebuild/verify the bundled catalog only if the existing schema lacks fields required by the profile; keep source provenance intact.
- [ ] **Step 5: Run catalog tests.

### Task 3: Deterministic interval scheduler

**Files:**
- Modify: `astrochecker/planner.py`
- Test: `tests/test_idea_planner.py`

- [ ] **Step 1: Write failing tests for two-hour filtering, full/partial/none status, priority tie-breaks, no interval merging, and deterministic output.
- [ ] **Step 2: Run the focused tests and confirm failure.
- [ ] **Step 3: Implement `plan_ideas(candidates, darkness_intervals, total_seconds, minimum_block_seconds=7200)` using supplied intervals only.
- [ ] **Step 4: Run focused tests and confirm green.

### Task 4: Local ideas service and API

**Files:**
- Modify: `astrochecker/service.py`
- Modify: `astrochecker/server.py`
- Test: `tests/test_local_acceptance.py`, `tests/test_local_backend.py`

- [ ] **Step 1: Write failing API acceptance tests for `/api/ideas`, validation, local-only execution, and explicit notes for partial/no plans.
- [ ] **Step 2: Run them and confirm failure.
- [ ] **Step 3: Implement request validation and service orchestration using the existing ephemeris and a coarse planning grid, refining chosen blocks with existing calculations where practical.
- [ ] **Step 4: Run API and acceptance tests.

### Task 5: UI flow

**Files:**
- Modify: `astrochecker/static/index.html`
- Modify: `astrochecker/static/app.js`
- Modify: `astrochecker/static/style.css`
- Test: `tests/test_local_ui.py`

- [ ] **Step 1: Add a failing browser acceptance test for the “Cerchi Idee?” button, loading state, plan rows, 2-hour label, and no-plan message.
- [ ] **Step 2: Run it and confirm failure.
- [ ] **Step 3: Add the button and compact plan card without changing the existing single-target layout.
- [ ] **Step 4: Run the browser test and fix regressions.

### Task 6: Documentation and release

**Files:**
- Modify: `README.md`, `ASTROCHECKER.md`, `CHANGELOG.md`, `ALPHA.md`
- Test: full suite and live smoke checks

- [ ] **Step 1: Document the two-hour minimum, astronomical/nautical darkness, 90-day limit, and suitability limits.
- [ ] **Step 2: Run the full test suite and live/browser verification.
- [ ] **Step 3: Verify Git identity, inspect the complete diff, commit on the feature branch, merge into `main`, tag the release, push, and publish the release notes.
