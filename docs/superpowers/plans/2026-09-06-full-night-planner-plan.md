# Full-Night Session Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic `Cerchi Idee?` plan that covers the complete astronomical night with an ordered target sequence and a dedicated output, while adding proposal acknowledgement and reliable datetime-picker closure.

**Architecture:** The service derives a local-noon anchor and astronomical-night envelope, the existing astronomy layer supplies five-minute target windows, and a pure planner optimizes chronological blocks using coverage-first deterministic scoring. The API exposes a future-export-ready plan; vanilla HTML/CSS/JS renders a dedicated night state while leaving the single-target path intact.

**Tech Stack:** Python 3.13, SQLite, Astropy, stdlib HTTP server, vanilla HTML/CSS/JS, pytest 9, Playwright 1.62.

**Spec:** `docs/superpowers/specs/2026-09-06-full-night-planner-design.md`

## Global Constraints

- Plan exactly the astronomical-darkness interval from evening twilight to morning twilight for the selected civil evening date.
- Use the existing local catalog and offline ephemerides; add no network or LLM calls.
- Use a 300-second planning grid and 7,200-second preferred target blocks.
- Maximize coverage first, then target priority, then fewer changes; keep deterministic ties.
- Preserve the existing single-target `/api/check` behavior and acceptance suite.
- NINA export remains disabled future work; expose sufficient plan data but create no NINA artifact.
- Proposal acknowledgement is session-only and has no backend effect.
- Do not add attribution or alter Git identity.

---

### Task 1: Astronomical-night envelope

**Files:**
- Modify: `astrochecker/planner.py`
- Modify: `astrochecker/service.py`
- Test: `tests/test_idea_planner.py`
- Test: `tests/test_ideas_api.py`

**Interfaces:**
- Produces: `observing_night_anchor(start: datetime, timezone_name: str) -> datetime` in `service.py`.
- Produces: `select_astronomical_night(intervals: list[dict], horizon_seconds: int = 86400) -> dict | None` in `planner.py`.
- Consumers: Task 2 planner and Task 3 service response.

- [ ] **Step 1: Write failing planner tests**

```python
def test_select_astronomical_night_uses_complete_evening_to_morning_interval():
    intervals = [{"start": 22000, "end": 51000}]
    assert select_astronomical_night(intervals) == {"start": 22000, "end": 51000}

def test_select_astronomical_night_returns_none_when_sun_never_reaches_minus_18():
    assert select_astronomical_night([]) is None
```

- [ ] **Step 2: Run `python -m pytest tests/test_idea_planner.py -q`** and confirm import/test failure because `select_astronomical_night` does not exist.
- [ ] **Step 3: Implement `select_astronomical_night`** as a pure normalized-interval selector that rejects edge-truncated fragments and chooses the first complete interval within the local-noon horizon.
- [ ] **Step 4: Write a failing service test** asserting that `2026-09-06T02:27` in `Europe/Rome` anchors the ideas horizon at `2026-09-06T12:00:00+02:00`, while the single-target parser remains unchanged.
- [ ] **Step 5: Run the focused service test** and confirm the anchor is still the supplied time.
- [ ] **Step 6: Implement `observing_night_anchor`** using `parse_start(f"{start.date().isoformat()}T12:00", timezone_name)` and use it only from `AstroCheckerService.ideas`.
- [ ] **Step 7: Run Task 1 tests** and confirm green.
- [ ] **Step 8: Commit** with `feat: define complete astronomical night envelope` after checking Git identity.

### Task 2: Coverage-first target-chain planner

**Files:**
- Modify: `astrochecker/planner.py`
- Test: `tests/test_idea_planner.py`

**Interfaces:**
- Consumes: candidates with `name`, `type`, `ra_deg`, `dec_deg`, `aliases`, `profile`, and `intervals`; one `night_interval` with integer offsets.
- Produces: `plan_night_sequence(candidates, night_interval, *, slot_seconds=300, preferred_block_seconds=7200) -> dict` matching the spec.
- Consumers: `AstroCheckerService.ideas` and UI/API tests.

- [ ] **Step 1: Write failing chain tests**

```python
def test_night_sequence_chains_complementary_targets_across_the_whole_night():
    candidates = [
        candidate("X", 30, 0, 10800),
        candidate("Y", 20, 10800, 21600),
        candidate("Z", 10, 21600, 28800),
    ]
    result = plan_night_sequence(candidates, {"start": 0, "end": 28800})
    assert [b["target"]["name"] for b in result["blocks"]] == ["X", "Y", "Z"]
    assert result["status"] == "full"
    assert result["covered_duration_seconds"] == 28800
    assert result["gaps"] == []
```

- [ ] **Step 2: Add failing cases** for an unavoidable gap, deterministic priority tie, a high-priority target not displacing greater coverage, no available targets, non-overlapping blocks, and a labelled short edge fill.
- [ ] **Step 3: Run `python -m pytest tests/test_idea_planner.py -q`** and confirm failures are due to the missing planner.
- [ ] **Step 4: Implement slot preparation** that clips every candidate interval to the night, emits 300-second slots, and preserves canonical target metadata.
- [ ] **Step 5: Implement dynamic programming** whose state tracks current target and consecutive slots; compare paths lexicographically by covered seconds, priority-seconds, negative short-block penalty, negative transitions, then canonical signature.
- [ ] **Step 6: Collapse selected slots** into chronological blocks, derive gaps, label allowed sub-7,200-second edge/bridge fills, and compute coverage percentage.
- [ ] **Step 7: Run focused planner tests** and confirm all green.
- [ ] **Step 8: Commit** with `feat: optimize a complete target chain` after checking Git identity.

### Task 3: Full-night ideas API

**Files:**
- Modify: `astrochecker/service.py`
- Modify: `astrochecker/server.py`
- Test: `tests/test_ideas_api.py`
- Test: `tests/test_local_acceptance.py`
- Test: `tests/test_local_backend.py`

**Interfaces:**
- Consumes: `observing_night_anchor`, `select_astronomical_night`, `plan_night_sequence`, current catalog candidates, and current ephemeris builders.
- Produces: `POST /api/ideas` response with `night_start`, `night_end`, `night_duration_seconds`, `covered_duration_seconds`, `coverage_percent`, `blocks`, `gaps`, `timezone`, and explanatory notes.

- [ ] **Step 1: Replace the protected ideas expectation with the approved behavior**: the selected date plans the complete evening astronomical night and ignores `duration_minutes` as plan length.
- [ ] **Step 2: Add a failing API test** where complementary catalog targets generate `X -> Y -> Z` absolute ISO timestamps bounded by twilight.
- [ ] **Step 3: Add failing API tests** for no astronomical night, unavoidable gaps, balcony-filtered candidates, retained offset fields, and canonical target coordinates/aliases.
- [ ] **Step 4: Run `python -m pytest tests/test_ideas_api.py tests/test_local_acceptance.py tests/test_local_backend.py -q`** and confirm expected contract failures.
- [ ] **Step 5: Refactor `AstroCheckerService.ideas`** to build darkness and all target ephemerides from local noon, select the complete night, and call `plan_night_sequence`.
- [ ] **Step 6: Convert offsets to aware ISO timestamps** without removing `offset_start` or `offset_end`; return explicit `none` data when no complete astronomical night exists.
- [ ] **Step 7: Keep request compatibility** by accepting the shared duration field while documenting that it controls only `/api/check`.
- [ ] **Step 8: Run Task 3 tests** and confirm green.
- [ ] **Step 9: Commit** with `feat: expose full-night ideas plans` after checking Git identity.

### Task 4: Dedicated night-plan output

**Files:**
- Modify: `astrochecker/static/index.html`
- Modify: `astrochecker/static/app.js`
- Modify: `astrochecker/static/style.css`
- Test: `tests/test_local_ui.py`

**Interfaces:**
- Consumes: Task 3 API response.
- Produces: `#night-plan` result state, `#night-chain`, `#night-timeline`, `#night-blocks`, `#night-gaps`, and disabled `#export-night-nina` action.

- [ ] **Step 1: Write a failing browser test** that clicks `Cerchi Idee?` and expects a `Piano della notte` heading, twilight bounds, 100% coverage, `X -> Y -> Z`, three ordered rows, and a segmented timeline.
- [ ] **Step 2: Add failing browser cases** for visible gaps, no astronomical night, short-fill badge, responsive containment, and the disabled NINA action.
- [ ] **Step 3: Run the selected Playwright tests** and confirm the dedicated state is absent.
- [ ] **Step 4: Add semantic night-plan markup** separate from `#result-content`; update labels so the selected civil date clearly identifies the evening being planned.
- [ ] **Step 5: Implement `renderNightPlan(data)`** using DOM creation and `textContent`, hiding the single-target state and rendering chain, coverage, blocks, gaps, and proportional timeline segments.
- [ ] **Step 6: Add responsive CSS** consistent with the existing design system and verify no horizontal overflow at current desktop/mobile test widths.
- [ ] **Step 7: Run Task 4 tests** and confirm green.
- [ ] **Step 8: Commit** with `feat: add dedicated night plan view` after checking Git identity.

### Task 5: Proposal acknowledgement and picker closure

**Files:**
- Modify: `astrochecker/static/index.html`
- Modify: `astrochecker/static/app.js`
- Modify: `astrochecker/static/style.css`
- Test: `tests/test_local_ui.py`

**Interfaces:**
- Produces: suggestion control with `aria-pressed`, selected class, and live text `Proposta acquisita`.
- Produces: `releaseDateTimePickerFocus(event)` handling complete minute values on `input` and `change`.

- [ ] **Step 1: Write a failing acknowledgement test** that renders a suggestion, activates it by mouse and keyboard, and asserts `aria-pressed="true"`, selected styling, and the exact live message `Proposta acquisita` without a network request.
- [ ] **Step 2: Write a failing picker test** that focuses `#start`, assigns `2026-09-05T23:17`, dispatches `input`, and expects focus to leave the control while the value remains unchanged.
- [ ] **Step 3: Add a keyboard regression** where an incomplete datetime value does not force blur.
- [ ] **Step 4: Run the selected browser tests** and confirm acknowledgement and `input` closure fail under current code.
- [ ] **Step 5: Make the suggestion card an accessible button** and keep selected proposal state in JavaScript memory, clearing it at the start of every new calculation.
- [ ] **Step 6: Implement one scheduled focus-release handler** for complete minute values on both `input` and `change`; preserve all form validation and stale-result behavior.
- [ ] **Step 7: Run Task 5 tests** and confirm green.
- [ ] **Step 8: Commit** with `fix: acknowledge proposals and close datetime picker` after checking Git identity.

### Task 6: Release documentation and integrated verification

**Files:**
- Modify: `astrochecker/static/index.html`
- Modify: `ASTROCHECKER.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/index.html`
- Create: `VERIFICA-NIGHT-PLANNER.md`

**Interfaces:**
- Produces: release `v0.4.0-alpha.1` documentation and evidence.

- [ ] **Step 1: Update visible version strings and documentation** to explain full astronomical-night planning, balcony-aware chaining, gaps, short fills, session-only acknowledgement, picker behavior, and future-but-disabled NINA export.
- [ ] **Step 2: Run focused tests**:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_idea_planner.py tests\test_ideas_api.py tests\test_local_backend.py tests\test_local_acceptance.py tests\test_local_ui.py -q
```

- [ ] **Step 3: Run the full suite**:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] **Step 4: Run syntax checks**:

```powershell
.\.venv\Scripts\python.exe -m compileall -q astrochecker tests
node --check astrochecker\static\app.js
```

- [ ] **Step 5: Run a live localhost smoke test** using the real catalog and ephemerides; verify `/api/ideas` returns a twilight-bounded plan and the browser renders its chain without console errors.
- [ ] **Step 6: Record exact test counts, timings, smoke inputs, output coverage, and known limits** in `VERIFICA-NIGHT-PLANNER.md`.
- [ ] **Step 7: Inspect `git diff --check`, complete diff, status, and effective Git identity**; ensure no AI attribution, secrets, runtime profile, wheel, or generated browser artifact is tracked.
- [ ] **Step 8: Commit release metadata** with `release: prepare v0.4.0-alpha.1`.
- [ ] **Step 9: Perform an independent review** of acceptance coverage, algorithm correctness, UI safety, and the complete feature diff; fix findings through new red-green cycles and rerun affected gates.
- [ ] **Step 10: Merge the verified feature branch into `main`**, rerun the full suite on the merge result, tag `v0.4.0-alpha.1`, push `main` and the tag, and publish a GitHub release whose notes match the verified behavior and limitations.
