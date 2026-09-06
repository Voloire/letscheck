# AstroChecker notes

AstroChecker checks whether a selected deep-sky target is visible from a saved observing site during the next 24 hours. It also offers a local idea planner for a complete astronomical night.

The bundled catalog contains Messier, NGC, IC, Sharpless (Sh2), van den Bergh (vdB), and Lynds (LDN) records. Search accepts catalog IDs, aliases, and common names. Cross-catalog groups expose related IDs and a shared nickname while preserving exact-ID resolution.

Visibility uses ICRS coordinates, geometric altitude and azimuth, and astronomical darkness (Sun at or below −18°). Refraction, weather, Moon position, sky quality, and equipment are outside the experiment’s scope. Results are estimates; the one-second decision grid is a computation detail, not a claim of one-second astronomical accuracy.

When a result needs a different window, the local planner returns up to three
real alternatives. They are ranked as **The Best** and additional alternatives
with an explainable one-to-five-star fit score. Selecting an option only
highlights it; the user must accept the option before export is enabled.

The accepted option can be given a custom sequence name and exported as a
native `CaptureSequenceList` XML file for NINA's Legacy/Simple Sequencer in the
current user's `Downloads` folder. The file contains the target in J2000 and a
STANDARD sequence with 300-second LIGHT exposures. The exposure count is the
integer number of complete exposures that fits the accepted window. Gain,
offset, filter, binning, dithering, and workflow switches stay at NINA's
defaults. NINA Legacy does not store the astronomical window in this file, so
apply the accepted start and end time manually.

All primary calculations run locally after dependencies and bundled data are present. The optional browser geolocation button can query the browser’s location service, but manual coordinates always remain available.
