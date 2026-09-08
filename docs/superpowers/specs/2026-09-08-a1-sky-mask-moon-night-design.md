# A1 design: sky mask, Moon and the night chain

Date: 2026-09-08. Status: approved in conversation by the owner, section by section.
Part of roadmap A (make the balcony persona real in the web app), first of four
sub-projects: A1 this document, A2 capture ("photo, finger, ok"), A3 the single
screen, A4 towards NINA. Context: `docs/superpowers/spikes/2026-09-08-nina-plugin.md`.

## Purpose

Give the planner a true model of the user's sliver of sky, treat the Moon as a wall or
a malus depending on the filter, and turn the night into a chain of targets bounded by
that sliver, exposed through a versioned API that browser, LAN bridge (B) and NINA
plugin (C) all consume. Backend only; no user interface changes.

## Persona and principles

The user shoots deep sky from an urban balcony through a sliver of sky, sets up (or
uncovers a rig left in place), starts NINA and goes to sleep. Beginner first, "don't make
me think": the server returns structured facts, the client turns them into plain
sentences. Honest answers over clever ones: "not from here", "almost nothing tonight".

## Section 1: the sky mask

- `SkyMask` is the union of one or more **pieces**; each piece is a closed polygon in sky
  coordinates, vertices in degrees `(azimuth, altitude)`. One piece per photo (A2). The
  closed polygon carries buildings below and the balcony ceiling above with no special
  cases.
- **Compiled form.** On construction the mask is rasterised into **720 azimuth columns of
  0.5 degrees**, each holding the sorted list of visible altitude intervals. `contains(az,
  alt)` is a table lookup, so the 86,400 per-second evaluations of a target cost what
  they cost today. Half a degree is ten times finer than the capture precision.
- **Today's rectangle is a special case**: the four fields `az_start`, `az_end`,
  `min_alt`, `max_alt` become one rectangular piece. Existing tests keep passing with
  identical results; the current interface keeps working until A3 replaces it.
- **Single entry point.** The visibility solver receives a mask and asks
  `contains(az, alt)`. The four loose variables spread across `service.py` and
  `planner.py` are replaced by the object.
- **Field-of-view margin.** The compiled mask can be **eroded** by a margin equal to half
  the diagonal of the rig's field of view (about 2 degrees for the default rig), so the
  whole frame, not just the target centre, stays inside the sliver. Erosion happens once
  per request on the table: altitude intervals shrink by the margin, azimuth columns by
  `margin / cos(altitude)` approximated per column.
- **Transport.** JSON, versioned:
  `{"version": 1, "pieces": [{"points": [[az, alt], ...]}]}`. In A1 the server does not
  store it; it travels in the request like the four numbers do today.
- **NINA horizon export** (used by A2 and A4, defined here): for each azimuth the lowest
  visible altitude of the mask. The ceiling is lost, and the export says so in a comment
  line. The exact NINA custom-horizon file format is verified against NINA sources at
  implementation time.
- **Validation.** At least three vertices per piece, altitudes within 0..90, azimuths
  normalised to 0..360 with pieces crossing north split in two internally, degenerate
  polygons rejected with a human-readable message. Limits: at most 20 pieces of at most
  200 points each.

## Section 2: the Moon

- **Data.** Each target ephemeris gains, on the same interpolated knots used today, the
  Moon's azimuth and altitude, its illuminated fraction and the angular separation
  Moon-target. Astropy provides them without downloads, as it does for the Sun.
- **One rule, two severities.** The NINA community (Target Scheduler, Moon Angle) uses the
  Lorentzian minimum-separation rule: the fuller the Moon, the farther the target must be;
  near new Moon almost no constraint. Two calibrations live in code, not in the UI:
  - **Broadband: the Moon is a wall.** An instant is closed, like behind a building, when
    the Moon is above the horizon and the target is closer than the separation required for
    tonight's phase. At full Moon almost the whole sky closes; at new Moon nothing does.
  - **Narrowband: the Moon is a malus.** Same formula with more permissive parameters;
    instants stay open, but the window gets a **Moon factor** in 0..1 that lowers the stars
    and is reported as a duration of Moon proximity.
- **The Moon inside the sliver.** Using the mask, compute when the Moon itself is inside the
  shape and report the interval.
- **Tonight's Moon summary** in every response: illumination, rise and set within the night,
  maximum altitude, inside or near the mask.
- **Alternative windows are Moon-aware.** The future search (up to 90 days today) applies the
  same rule; the first alternative is labelled `next_without_moon`.
- **The switch** arrives as `profile.filter: "broadband" | "narrowband"`, default
  broadband: whoever does not choose gets the strict, honest version.

## Section 3: the night chain and alternatives

- **Night bounds.** Start: the later of `profile.ready_at` and the start of astronomical
  darkness. End: astronomical dawn. No end time is asked of the user.
- **Candidates.** Today's shortlist, filtered by the switch: narrowband proposes emission
  nebulae, planetary nebulae, supernova remnants; broadband proposes clusters, bright
  galaxies, bright nebulae. LDN dark nebulae and faint objects leave the proposals and stay
  searchable by hand with a `hard_from_city` flag.
- **Per-candidate visibility.** Open instants are those inside the (eroded) mask and not
  closed by the Moon; in narrowband the Moon factor is attached. Intervals at the 5-minute
  step used today for the shortlist.
- **The chain.** The coverage-first algorithm stays with two changes: the minimum block
  drops from 2 hours to **1 hour**, because a sliver is narrow, and each block ends exactly
  when the target leaves, not at a round time. Blocks carry start and end to the second:
  these are what A4 hands to NINA.
- **Why each block ends.** Looking at which constraint fails in the next instant, each
  block explains its end with a code: `mask_side` with a compass direction, `mask_ceiling`,
  `dawn`, `moon`. Gaps carry the same code when a single cause applies.
- **Rig and framing.** `profile.rig` defaults to 400 mm focal length on an APS-C sensor
  (23.5 x 15.6 mm): field 3.4 x 2.2 degrees, diagonal about 4 degrees. Each target gets a
  `framing` code from the catalog's size: `fits`, `small`, `mosaic`. The rig also sets the
  mask erosion margin (Section 1).
- **Single-target check** uses the same machinery: tonight's intervals with end reasons; if
  the target never enters the mask within 90 days, `never_here` is true and `similar` lists
  the three objects of the same type that pass best tonight.
- **Alternatives.** Up to three within 90 days that satisfy requested duration, mask and
  Moon rule, ranked by today's stars multiplied by the Moon factor.
- **Deterministic.** Same request, same chain. Existing chain tests stay valid with a
  rectangle and the Moon rule disabled.

## Section 4: API v1 contract

The server speaks in **codes and numbers**, never sentences. Clients (browser in A3,
plugin in C) compose the user's language.

- **Path** `/api/v1/...`, JSON over POST. Legacy `/api/check` and `/api/ideas` stay
  untouched until A3 retires them.
- **Common context** in every request: `site` (latitude, longitude, timezone), `mask`
  (Section 1, optional: absent means whole sky), `profile` (`filter`, optional `ready_at`
  as local "HH:MM", optional `rig` with `focal_length_mm` and `sensor_mm: [w, h]`),
  `date` (the observing night, default today at the site).
- **`POST /api/v1/night`**: night bounds, Moon summary, blocks (target, start and end in
  ISO 8601 with offset, duration in seconds, `ends_because`, `framing`, `moon_factor`,
  `stars`), gaps with the same reason codes.
- **`POST /api/v1/check`**: tonight's intervals with end reasons, `never_here`, up to three
  `alternatives` (date, start, end, stars, moon_factor, label), `similar`.
- **`GET /api/v1/objects?q=`** (today's search) and **`GET /api/v1/status`**.
- **`POST /api/v1/horizon`**: mask in, NINA horizon file out as text. One implementation
  for browser and plugin.
- **Reserved for A4** so names never change: `POST /api/v1/plans` returns a code,
  `GET /api/v1/plans/{code}`, `GET /api/v1/plans/{code}/nina.json`.
- **Errors** in today's shape `{"error": ..., "code": ...}` with stable codes and the
  offending field when there is one. Payload limits as in Section 1.
- **Units** always the same: degrees, seconds, ISO 8601. Nothing localised server-side.
- **Security** as today: same Host rule, same Origin rule. The server stays stateless in A1.

## Section 5: errors, tests, boundaries

- **Honest errors, never fake windows.** Invalid mask: rejected naming the piece and the
  reason. Missing site: rejected. No astronomical night (June in Milan): the response says
  so with `no_astronomical_night` and the chain uses nautical twilight, declaring it.
  Astronomy data unavailable: 502 as today.
- **Tests, three levels.**
  1. **Unit tests on the core**, no network, no browser: the mask (rectangle equals today's
     four numbers, pieces crossing north, ceiling, erosion), the Moon rule (full Moon closes
     broadband, new Moon does not, narrowband never closes), end reasons, the chain with a
     1-hour block.
  2. **Fixed real cases**: the owner's balcony as the first test case, with the real mask,
     the FRA400 rig, one full-Moon date and one new-Moon date. Expected results frozen after
     one manual review.
  3. **API contract**: every v1 endpoint with example request and response saved as files,
     which the C# plugin will use as fixtures. Today's 260 tests stay green because legacy
     endpoints do not change.
- **Performance**: same order of magnitude as today. The mask is a table, the Moon one more
  interpolation, erosion once per request.
- **Out of A1**, explicitly: user interface (A2, A3), NINA JSON export and expiring share
  codes (A4), weather, refraction, a real site horizon beyond the mask, accounts, and the
  Spiraglio rename in the interface (A3).

## Open items to verify at implementation

- NINA custom horizon file format (from NINA sources).
- Lorentzian parameters: start from Target Scheduler defaults for broadband and a more
  permissive pair for narrowband; freeze after the owner's balcony cases are reviewed.
- Catalog size fields available for the `framing` code (`major_axis_arcmin` and friends).
