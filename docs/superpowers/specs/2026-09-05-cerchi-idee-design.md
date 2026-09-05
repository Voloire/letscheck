# Cerchi Idee? Design

## Goal
Build a deterministic local session planner that proposes an amateur-friendly multi-object DSO sequence from the SQLite catalog, respecting the saved observing window and a two-hour minimum continuous block per object.

## Rules
- All open/ globular/other catalogued clusters are eligible.
- Emission and reflection nebulae have highest priority; large bright nebulae remain eligible whenever catalog data supports them.
- Beginner objects receive a priority boost.
- Compact galaxies are eligible; clearly extended galaxies are excluded from automatic ideas in this first version.
- Unknown, stellar, duplicate, and incomplete records are excluded, with a reason.
- The planner maximizes covered imaging time first, then priority, then continuity and fewer target changes. Object count is an output.
- Darkness is reported with astronomical and nautical envelopes; astronomical darkness is the default DSO validity criterion.
- The search horizon is at most 90 days, reusing the existing limit.
- No LLM, network call, NINA export, weather, Moon, or equipment simulator is added.

## Output
The ideas endpoint returns one deterministic plan with status (`full`, `partial`, `none`), requested and covered duration, darkness mode, blocks (object, type, start, end, duration, priority, reason), skipped counts, and an explanatory note.
