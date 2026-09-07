# Changelog

## Unreleased

- Added an opt-in cloud mode for running behind an HTTPS proxy such as Cloud Run:
  `--host`, the `PORT` variable and `ASTROCHECKER_PUBLIC_HOST` in `run.py`, host and
  https-origin checks instead of the loopback check, no site file on the server and
  NINA sequences delivered as XML downloads.
- Added `localStorage` fallback for the observing site when the server keeps none.
- Added a `Dockerfile` with a digest-pinned Python base image and a `.dockerignore`.
- Added a responsive candidate limit for Need Ideas so broad filters cannot
  leave the page waiting while every catalog record is evaluated.
- Added native NINA Legacy target-set XML export for a complete Need Ideas plan,
  with a user-defined sequence name and ordered targets.
- Added a defensive astronomical-darkness intersection before ranking window
  suggestions and fixed same-period widest-window offsets.
- Promoted each proposal's continuous duration into the card summary.
- Updated the default unsaved site to generic central Rome coordinates and
  added the small “Balcony Stargazer” product nickname.
- Added up to three ranked observing-window alternatives with one-to-five-star fit scores.
- Added explicit proposal acceptance and custom naming before local NINA XML export.
- Added visible export success and retryable error states for named NINA sequences.
- Added local common-name search and cross-catalog target groups.
- Added related identifiers and nickname metadata to API, planner, and UI results.
- Added native NINA Legacy/Simple Sequencer XML export from accepted observing-window suggestions.
- Linked adjusted suggestions to the green timeline and exposed each window's full continuous duration.
- Moved published copy and documentation to friendly US English.
