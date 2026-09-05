# Full-Night Session Planner Design

## Goal

Transform `Cerchi Idee?` from a short-duration suggestion into an operational plan for the complete astronomical night. The result must tell a balcony astrophotographer which locally visible targets to chain, in chronological order, from evening astronomical twilight to morning astronomical twilight.

The existing single-target calculation remains available and unchanged. NINA export remains future work, but this release establishes a stable plan structure that can later be translated without recomputing the night.

## Observing-night contract

- The civil date in `Data e ora della postazione` identifies the evening date to plan. The time remains meaningful to the single-target calculator but is ignored by `Cerchi Idee?`.
- The service anchors the ideas calculation at local noon on that civil date and searches the following 24 physical hours.
- The planned envelope is the first continuous interval in that horizon where the Sun is at or below -18 degrees: evening astronomical twilight to morning astronomical twilight.
- If no astronomical night exists at that location and date, the result is `none` and explains why. Nautical darkness may still be reported as context but must not silently replace the selected criterion.
- All target windows are clipped to the astronomical-night envelope and to the saved altitude/azimuth balcony limits.

## Sequence objective

The planner works on the existing five-minute deterministic ephemeris grid and returns an ordered chain such as `X -> Y -> Z`.

The optimization order is:

1. maximize covered astronomical-darkness time;
2. minimize avoidable gaps;
3. prefer higher catalog/profile priority targets;
4. prefer fewer target changes and longer continuous blocks;
5. break remaining ties deterministically by time and canonical object name.

Two hours (7,200 seconds) is the preferred minimum block for a target, not the requested duration of the entire plan. Internal blocks shorter than two hours are rejected when a valid longer assignment exists. A shorter edge or bridge block is permitted only when it increases useful night coverage and cannot be extended to two hours within that target's visibility window. The response identifies such a block as `short_fill` so the compromise is visible.

No weather, Moon, equipment model, meridian flip, filter plan, slew time, autofocus, or NINA sequencing is inferred in this release.

## Planner interface

Add a pure planner entry point:

```python
plan_night_sequence(
    candidates,
    night_interval,
    *,
    slot_seconds=300,
    preferred_block_seconds=7200,
) -> dict
```

Each candidate supplies canonical identity, display metadata, priority, reason, and one or more visibility intervals expressed as offsets from the local-noon anchor. The planner performs no astronomical calls.

The result contains:

```json
{
  "status": "full",
  "night_start": 24120,
  "night_end": 52680,
  "night_duration_seconds": 28560,
  "covered_duration_seconds": 28560,
  "coverage_percent": 100,
  "preferred_block_seconds": 7200,
  "blocks": [
    {
      "target": {
        "name": "NGC 7000",
        "type": "HII",
        "ra_deg": 314.0,
        "dec_deg": 44.0,
        "aliases": ["North America Nebula"]
      },
      "start": 24120,
      "end": 34920,
      "duration_seconds": 10800,
      "priority": 30,
      "reason": "Nebulosa a emissione visibile dal balcone.",
      "short_fill": false
    }
  ],
  "gaps": []
}
```

The service converts block and gap offsets to timezone-aware ISO timestamps while retaining `offset_start` and `offset_end`. Canonical name, coordinates, type, aliases, start, and end form the future NINA-export boundary; no NINA file or command is produced now.

## Service and API

`POST /api/ideas` keeps the existing route but changes its successful response to the full-night contract. It:

1. validates the shared site and balcony fields;
2. derives local noon from the selected civil date and IANA timezone;
3. computes astronomical and nautical darkness for the following 24 hours;
4. selects the astronomical-night interval;
5. computes candidate visibility over the same anchor and horizon;
6. invokes the pure sequence planner;
7. returns absolute timestamps, coverage, blocks, gaps, limits, and explanatory notes.

The previous `duration_minutes` value is not used as the ideas-plan duration. It remains required for the single-target flow and may be accepted for backward request compatibility.

## Dedicated output

`Cerchi Idee?` opens a dedicated `Piano della notte` result state rather than appending a small card to the single-target result.

The state contains:

- the astronomical-night start, end, total duration, and coverage percentage;
- a prominent chronological chain summary (`X -> Y -> Z`);
- a horizontal night timeline with target-colored segments and explicit uncovered gaps;
- an ordered list with target, type, start/end, duration, reason, and a badge for short fill blocks;
- a clear `none` state when astronomical darkness or usable targets are absent;
- a disabled `Esporta in NINA` action labelled as future work.

Starting a single-target calculation hides the night-plan state. Starting `Cerchi Idee?` hides the single-target result state. Existing responsive styling and accessibility conventions are preserved.

## Proposal acknowledgement

The priority suggestion in the normal single-target result becomes an accessible button. Activating it:

- marks the proposal selected in current-page memory only;
- applies a selected visual state and `aria-pressed="true"`;
- displays `Proposta acquisita` in the live status area;
- performs no navigation, recalculation, persistence, or NINA action.

Selecting a different proposal replaces the acknowledgement. A new calculation clears it.

## Date/time picker behavior

The native `datetime-local` control must relinquish focus immediately after the browser reports a complete minute selection. The handler listens to the event actually emitted by the supported browser during minute selection (`input`, with `change` as fallback), schedules one focus release, and does not alter the selected value. Keyboard editing must remain possible: incomplete values are not blurred.

## Acceptance criteria

- A normal mid-latitude date produces a plan bounded by evening and morning astronomical twilight, independent of the entered duration minutes.
- Multiple complementary visibility windows produce an ordered `X -> Y -> Z` chain with non-overlapping blocks.
- Coverage, gaps, and status agree with the night envelope; unavoidable gaps are shown rather than hidden.
- Balcony altitude and azimuth limits change the candidate windows and therefore the sequence.
- The same inputs produce byte-for-byte stable block ordering and tie-breaking.
- No astronomical darkness produces an explicit no-night result.
- A short fill block is labelled and appears only when it increases otherwise uncovered useful time.
- The dedicated output renders the night summary, chain, timeline, rows, gaps, and future NINA affordance.
- Clicking a normal proposal produces the session-only acknowledgement and accessible selected state.
- Completing minute selection closes the native picker/focus without changing the chosen datetime.
- Existing single-target acceptance tests remain green.

## Release

Release as `v0.4.0-alpha.1`. Update the application header, user documentation, changelog, README release link, and public project page. Run focused planner/API/browser tests, the full suite, syntax checks, and a live localhost smoke test before merge, tag, push, and GitHub release publication.
