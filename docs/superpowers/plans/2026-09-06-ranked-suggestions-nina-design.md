# Ranked Suggestions and Named NINA Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Present one to three genuinely valid observing suggestions ranked with one to five stars, require explicit acceptance, and export the accepted plan as a named NINA Legacy XML sequence.

**Architecture:** Keep the deterministic local planner as the source of truth. Extend its suggestion generation to produce a bounded ranked list with explainable scores, expose the list through the existing check response, and make the browser flow explicit: choose, accept, name, export. The NINA endpoint validates the accepted target and duration and writes a sanitized, user-named XML file to the local Downloads directory.

**Tech Stack:** Python 3 standard library, existing local astronomy/planner service, vanilla JavaScript, HTML/CSS, pytest, Playwright.

**Spec:** Approved post-calculation UX requirements from the conversation on 2026-09-06.

## Global Constraints

- All calculations and exports remain local; no network service is introduced.
- Suggestions are real candidates only; return zero to three candidates and never pad the list with duplicates.
- Stars are an explainable fit score from one to five; `The Best` is the highest-ranked available candidate and is not forced to five stars.
- Export is enabled only after explicit acceptance of one candidate.
- NINA output remains native Legacy/Simple Sequencer XML with 300-second LIGHT exposures and existing NINA defaults.
- UI and user-facing documentation use friendly US English.
- New Git metadata must use Franco Geraci / 6276639+Voloire@users.noreply.github.com only.

---

### Task 1: Add ranked candidate generation and scoring

**Files:**
- Modify: `astrochecker/planner.py`
- Modify: `astrochecker/service.py`
- Test: `tests/test_suggestions.py`
- Test: `tests/test_backend.py`

**Interfaces:**
- Produce `choose_suggestions(...) -> list[dict]`, each item containing `tier`, `stars`, `score`, `start`, `end`, `duration_seconds`, `requested_duration_seconds`, `available_duration_seconds`, and `reason`.
- Preserve `choose_suggestion(...)` as a compatibility wrapper returning the first item or `None`.
- Check responses expose `suggestions` with zero to three serialized candidates.

- [x] Write failing tests for three deterministic candidates, fewer than three candidates, star bounds, and compatibility wrapper behavior.
- [x] Run the focused tests and confirm they fail because the list API and fields do not exist.
- [x] Implement deterministic candidate generation from current adjusted, future, and widest strategies, deduplicate by interval/tier, score fit against requested duration and recency, sort descending, cap at three, and map score to one through five stars.
- [x] Update the service to serialize the ranked list and generate a plural-aware note when no additional valid alternatives exist.
- [x] Run focused planner/backend tests and confirm they pass.

### Task 2: Replace implicit click-export with explicit acceptance and named export

**Files:**
- Modify: `astrochecker/static/index.html`
- Modify: `astrochecker/static/app.js`
- Modify: `astrochecker/static/style.css`
- Modify: `tests/test_local_ui.py`

**Interfaces:**
- UI renders `#suggestion-list`, candidate cards, `Accept this window`, `#accepted-plan`, `#nina-sequence-name`, `#export-accepted-nina`, and visible export feedback.
- Browser sends `{object, duration_seconds, suggestion_start, suggestion_end, sequence_name}` only after acceptance.

- [x] Add browser tests proving initial click only selects, acceptance enables export, name is sent, success shows filename/path, and export failure preserves accepted state.
- [x] Run the new tests and confirm they fail against the current single-card immediate-export flow.
- [x] Implement accessible ranked cards with text stars, explicit acceptance state, same-day timeline highlight for the accepted item, and a clear future-date message.
- [x] Add a name field with a safe default and client-side required validation; remove the old disabled “Export TARGET to NINA” action from the suggestion path.
- [x] Implement loading, success, and retryable error states without losing the accepted plan.
- [x] Run focused browser tests and confirm they pass.

### Task 3: Validate and persist user-named NINA Legacy sequences

**Files:**
- Modify: `astrochecker/nina.py`
- Modify: `astrochecker/service.py`
- Modify: `astrochecker/server.py`
- Test: `tests/test_nina.py`
- Test: `tests/test_local_backend.py`

**Interfaces:**
- `export_legacy_sequence(target, duration_seconds, sequence_name=None, downloads_dir=None, ...) -> dict`.
- API accepts optional `sequence_name`, sanitizes it for a filename, and returns `filename`, `path`, `exposure_seconds`, and `exposure_count`.

- [x] Add failing tests for custom names, unsafe filename characters, missing names, and preservation of XML target/exposure fields.
- [x] Run focused NINA tests and confirm the expected failures.
- [x] Implement name normalization with a deterministic fallback, collision-safe file writing, and API validation while preserving the native XML structure.
- [x] Run focused NINA/backend tests and confirm they pass.

### Task 4: Update copy, release metadata, and complete verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `ASTROCHECKER.md`
- Modify: `tests/test_local_ui.py` as needed for copy assertions

- [x] Update US English copy for ranked suggestions, explicit acceptance, and named local NINA export.
- [x] Run `pytest -q`, `python -m compileall astrochecker`, `node --check astrochecker/static/app.js`, and `git diff --check`.
- [x] Run the project release/build workflow and inspect generated artifacts.
- [x] Verify Git author/committer identity and commit without trailers or bot attribution.
- [x] Tag and push the release only after all checks pass.
