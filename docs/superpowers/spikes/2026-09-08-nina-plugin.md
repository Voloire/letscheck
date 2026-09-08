# Spike: AstroChecker as a NINA plugin, or integrated with NINA another way

Date: 2026-09-08. Research only, nothing built. Sources were fetched by two research
agents; items marked (U) could not be verified from a primary source.

## Question

Does it make sense to imagine AstroChecker ALSO as a N.I.N.A. plugin, next to the current
web app? How would it fit NINA's workflow, how hard is it, and would it help the owner's
visibility in the community?

## What AstroChecker is today

Python 3 web app (about 3,300 lines), MIT, public repo, live on Cloud Run. Bundled catalog
(Messier, NGC, IC, Sharpless, vdB, LDN), single-target visibility check under astronomical
darkness (Sun <= -18 deg) for the next 24 h, up to three alternative windows ranked 1-5
stars, "Need ideas?" full-night ordered target set, export to NINA Legacy XML
(`CaptureSequenceList`, `ArrayOfCaptureSequenceList`), Cartes du Ciel TCP client. No Moon,
weather, refraction, horizon or equipment model.

## How NINA plugins work (verified)

- C# class library, MEF exports, `net8.0-windows` + WPF for NINA 3.2 (develop is already
  net10). NuGet `NINA.Plugin` 3.2.0.9001. Template: github.com/isbeorn/nina.plugin.template.
- Extension points: `ISequenceItem`/`ISequenceTrigger`/`ISequenceCondition`/`ISequenceContainer`,
  `IDockableVM` (Imaging tab panel), Options page, `IPluggableBehavior`, `IEquipmentProvider`.
- Useful services: `IProfileService` (site lat/lon/elevation), `ISequenceMediator`
  (`AddAdvancedTarget(IDeepSkyObjectContainer)`, `AddTargetToTargetList`, `StartAdvancedSequence`),
  `NINA.Astrometry` (`NighttimeCalculator`, twilight, rise/set, `MoonInfo`).
- Publishing: PR to github.com/isbeorn/nina.plugin.manifests (manifest JSON, checksum, review).
  Closed source is refused; MPL-2.0 is the norm, MIT accepted. About 100 plugins listed for
  NINA 3 (davidmoulton.me/nina-plugins, 2026-09-07). No public download counts.
- Non-.NET payloads: JS web apps are bundled by some plugins (Web Session History Viewer,
  Touch'N'Stars). No published plugin bundles a Python runtime. Options for Python logic:
  spawn a process (PyInstaller exe), talk HTTP to a local or remote server, or pythonnet.

## Integration without a plugin (verified)

- Advanced Sequencer stores sequences, templates and targets as JSON (folders in
  Options > Imaging > Sequence). Legacy XML is the old path; still importable.
- Telescopius CSV import exists; Target Scheduler has bulk CSV import (own format and
  Telescopius). phtnnz/astro `nina-create-sequence2` generates Advanced Sequencer JSON from CSV.
- Advanced API plugin (christian-photo/ninaAPI, MPL-2.0, 48 stars, min NINA 3.3): REST +
  WebSocket, `sequence/load` accepts a full sequence JSON by POST, `framing/set-coordinates`,
  `sequence/set-target` edits an existing container, `sequence/start`. No route adds a new
  target container; POSTing a whole sequence is the workaround. Touch'N'Stars (122 stars)
  runs whole sessions through it, proof that an external app can drive NINA.

## Landscape: who already does what

| Tool | Author, state | Overlap with AstroChecker |
|---|---|---|
| Sky Atlas (built-in) | NINA | filter "visible for N minutes in time range", altitude chart with darkness bands, horizon, Moon phase; send to Sequencer/Framing |
| Target Planning plugin | tcpalmer, v3.2.2, 2026-06 | single-target daily/annual visibility with Moon (Lorentzian), twilight, min duration: the closest to the "check" |
| Tonight's Best plugin | CCDASTRO, v0.1, created 2026-09-04 | dockable top-15 for tonight, weighted score, hands off to Framing: the closest to "Need ideas?" |
| Lightbucket Astro Planner | desktop app, MIT, v1.2.2, 2026-04 | catalog, imaging window with Moon, multi-target night Gantt, exports `.ninaTargetSet`: very close to the whole app |
| Target Scheduler | tcpalmer, v5.10, 2026-06 | just-in-time execution engine with projects, horizon, Moon avoidance, scoring; steep learning curve |
| DynamicSequencer, Astro PM (paid) | | runtime target selection |
| Orbuculum | Stefan Berg, 2025 | loop conditions on next target hour angle/altitude; orders targets you already placed. Not a planner |
| Orbitals | G. Hilios, 2026-08 | comets/asteroids/planets tracking. Unrelated |
| Moon Angle | D. Ghent | Moon separation loop condition |

Gap analysis: the visibility check, the "what tonight" ranking, the night execution and the
NINA export all exist somewhere. Every competitor models the Moon; several use a custom
horizon. What AstroChecker has that they lack: zero-install web/mobile use away from the
imaging PC; the "not tonight, here are three later windows with stars" answer; Sharpless,
vdB and LDN catalogs beyond NINA's database.

## Where a plugin would sit in the NINA workflow

Today: plan on the phone or laptop with AstroChecker, download Legacy XML, copy it to the
imaging PC, load it in the Simple Sequencer, set start/end times by hand.

Plugin form (thin): Imaging tab dockable panel showing AstroChecker (WebView2 on the Cloud
Run URL or embedded static UI), site read from the active profile, a button that calls
`ISequenceMediator.AddAdvancedTarget` per target, so the plan lands in the Advanced Sequencer
with no file. Optionally Target Scheduler hand-off via its CSV.

Plugin form (full port): rewrite planner, catalog and scoring in C# on `NINA.Astrometry`.
Duplicates Sky Atlas, Target Planning and Tonight's Best; the largest effort and the least
new value.

## Effort

| Path | Skills and tooling | Size |
|---|---|---|
| A. Improve exports (Advanced Sequencer JSON, Target Scheduler CSV) + Moon + horizon, in the web app | Python only, current repo | small to medium, days |
| B. "Send to NINA" bridge through the Advanced API on the LAN (POST sequence JSON, `sequence/start`) | Python + JS, the user installs the Advanced API plugin | medium, a couple of weeks part time |
| C. Thin plugin: WebView2 panel + `ISequenceMediator` + Options page, manifest PR | C#/.NET 8/WPF, Windows, Visual Studio, a NINA test rig | medium, 2-4 weekends for someone at ease with C#; longer if learning |
| D. Full C# port | as C plus astronomy in C# | large, months; low differentiation |

## Visibility

The in-app Plugins tab is the adoption gate: two brand-new planning plugins (Tonight's Best,
Astro Coverage Planner) both ship "manual install until the marketplace listing lands". A
listed plugin puts a name in front of every NINA user who opens that tab; a web app is only
found through posts. Channels: NINA Discord (#plugin-discussions), Cloudy Nights "New
Freeware Announcements", Telescopius forum, YouTube reviewers (Patriot Astro, Cuiv) (U).
Alternative route to reputation: contribute Moon or window features to Tonight's Best or
Lightbucket Astro Planner rather than shipping the 101st plugin.

## Persona (added after the owner's review, 2026-09-08)

The target user is the urban, aspiring-to-intermediate astrophotographer shooting deep sky
from a balcony: a sliver of sky (an azimuth range between buildings, an altitude floor),
Bortle 7-9, a couple of hours on weeknights, gear set up and torn down every session, NINA
user, often narrowband. Every "best target tonight" tool surveyed assumes an open horizon,
a dark site and a whole night, which makes their answer useless for this person. This
reorders the product: the horizon mask (import/export in NINA's custom-horizon format) is
the central feature; alternative windows matter more; the catalog must be filtered for
light-polluted skies (LDN dark nebulae are unrealistic from a city); Moon weighting depends
on the filter; realistic session length is an input. A name carrying the idea was proposed:
"Spiraglio", confirmed by the owner the same day. Brand name Spiraglio for UI, docs and
domain (`spiraglio.voloirex.com`); internal identifiers (Cloud Run service, image, env var,
Python package) stay `astrochecker`, because renaming the service would be a replacement the
release policy forbids.

## Decision (owner, 2026-09-08)

Paths A and B are chosen; C only later with traction; D excluded. The developer is Claude
working with the owner, so the effort column above (weekends, part-time weeks) is a
human-effort reference only; the real constraint is owner review time and the tag/exposure
rule, not coding hours.

## Recommendation

1. Do A first, regardless: without Moon and horizon and without Advanced Sequencer JSON
   the app is not credible next to the tools above. All of it is Python, all of it
   benefits every later form.
2. Then B: it delivers the "phone to mount" experience that is AstroChecker's real
   differentiator, without C#. Validate interest on Discord and Cloudy Nights with this.
3. Only with traction, C as a thin plugin for the marketplace listing. Skip D.

## Sources

nighttime-imaging.eu/docs (plugins, skyatlas, framing, sequencer), github.com/isbeorn/nina
(ISequenceMediator.cs, NINA.Astrometry), github.com/isbeorn/nina.plugin.template,
github.com/isbeorn/nina.plugin.manifests, nuget.org/packages/NINA.Plugin,
github.com/christian-photo/ninaAPI, github.com/Touch-N-Stars, tcpalmer.github.io/nina-scheduler,
github.com/tcpalmer/nina.plugin.targetplanning, github.com/CCDASTRO/TonightsBest-NINA,
github.com/LightbucketAstro/lightbucket-astro-planner, github.com/isbeorn/nina.plugin.orbuculum,
github.com/ghilios/NINA.Joko.Plugin.Orbitals, github.com/daleghent/nina-moon-angle,
github.com/DanielHeEGG/DynamicSequencer, github.com/astro-roro/Astro-Coverage-Planner,
davidmoulton.me/nina-plugins, kstars-docs.kde.org (Ekos Scheduler), github.com/pythonnet/pythonnet.
