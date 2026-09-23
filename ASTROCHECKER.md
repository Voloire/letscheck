# AstroChecker notes

AstroChecker checks whether a selected deep-sky target is visible from a saved observing site during the next 24 hours. It also offers a local idea planner for a complete astronomical night.

The bundled catalog contains Messier, NGC, IC, Sharpless (Sh2), van den Bergh (vdB), and Lynds (LDN) records. Search accepts catalog IDs, aliases, and common names. Cross-catalog groups expose related IDs and a shared nickname while preserving exact-ID resolution.

Visibility uses ICRS coordinates, geometric altitude and azimuth, and astronomical darkness (Sun at or below −18°). Refraction, weather, Moon position, sky quality, and equipment are outside the experiment’s scope. Results are estimates; the one-second decision grid is a computation detail, not a claim of one-second astronomical accuracy.

When a result needs a different window, the local planner returns up to three
real alternatives. They are ranked as **The Best** and additional alternatives
with an explainable one-to-five-star fit score. Each card shows its continuous
duration next to the rank and stars. A calculated interval can be selected
directly; ranked alternatives still require explicit acceptance before export.

The accepted option can be given a custom sequence name and exported as a
native `CaptureSequenceList` XML file for NINA's Legacy/Simple Sequencer in the
current user's `Downloads` folder. The continuous-window list is also directly
selectable: selecting one opens an explicit format chooser for a single target,
a target set, or the manual composer. The composer lets the user edit ordered
target blocks, coordinates, block durations, and exposure times; it does not
generate additional targets or automatic suggestions. The **Need ideas?** planner can instead
export the complete ordered target set as NINA's native
`ArrayOfCaptureSequenceList` XML. Each target contains J2000 coordinates and a
STANDARD sequence with 300-second LIGHT exposures. The exposure count is the
integer number of complete exposures that fits that target's planned block.
Single targets are written as `.xml`; target sets are written as NINA's
`.ninaTargetSet` format with the XML Schema declarations required by NINA.
Gain, offset, filter, binning, dithering, and workflow switches stay at NINA's
defaults. NINA Legacy does not store the astronomical window in these files,
so apply the planned start and end times manually.

The exporter is deliberately limited to the Legacy/Simple Sequencer fields
shown in N.I.N.A.'s user guide: target coordinates and rotation, exposure
progress/total, exposure time and type, binning, dither, gain, and offset.
It does not emit Advanced Sequencer entities, planner metadata, Moon data,
mask data, or unrecognised XML fields. Advanced Sequencer `.json` export is not
implemented yet.

All primary calculations run locally after dependencies and bundled data are present. The optional browser geolocation button can query the browser’s location service, but manual coordinates always remain available.
