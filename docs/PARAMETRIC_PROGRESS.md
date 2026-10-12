# Parametric refactor — progress

Plan: `PARAMETRIC_PLAN.md`. Update this file at the end of every session.

## Status

| Milestone | State | Notes |
|---|---|---|
| M0 Scaffolding | done 2026-10-11 | `dim.py` + unit tests, `binParameters.py`, 29 `gfbN_*` params (always created) |
| M1 Height chain | done 2026-10-11 | `bin_height_u`, `height_unit` live; verified in Fusion (12/12) |
| M2 Footprint scalars | not started | |
| M3 Feature scalars | not started | |
| M4 X/Y count (feature pattern) | not started | |
| M5 Baseplate | not started | |

## How to test

- Unit: `python3 -m unittest discover -s tests` (repo root, plain Python).
- In Fusion: run through the fusion MCP (`mcp__fusion__fusion_mcp_execute`, `featureType: script`):
  ```python
  import runpy
  def run(_context: str):
      runpy.run_path('/Users/dlouw/Developer/FusionGridfinityGenerator/tests/fusion/bin_parameters_test.py')['run'](_context)
  ```
  It imports the repo's real `generateBin()` fresh (purges cached modules), drives it with stub
  dialog inputs in scratch documents, edits parameters, and checks health, height, body count and
  **edited-vs-freshly-created equivalence (volume + face count)**. Scratch docs are closed at the end.
  Add a case there for every new live parameter.

## Lessons (also folded into the plan / CLAUDE.md)

- Timeline groups report `healthState == 5` with an empty message — they have no health of their
  own. Check the group's members instead (upstream bins show the same).
- Scoop topology: if the scoop fillet radius equals the full compartment depth, the scoop consumes
  the whole wall face and the later vertical-edge fillet loses its edges when height changes.
  When parametric, the scoop is capped at `depth - BIN_SCOOP_MIN_TOP_WALL` (0.5 mm); the
  plain-value path (still used by the baseplate) is unchanged from upstream.
- Compartments whose requested depth is >= the bin's full depth now follow the bin height
  (`binBodyGenerator`); shallower custom compartments use `min(full depth; requested)`.

## Log

- 2026-10-11 — Forked, cloned, branch `parametric-user-parameters`, symlinked into Fusion AddIns
  as `GridfinityGeneratorParametric` (own GUID / command ids, v2.0.0.0). Plan written.
- 2026-10-11 — M0 + M1 implemented and verified in Fusion: 12/12 in-Fusion checks (default,
  scoop+tab+notches+2x2+magnets+screws, no-lip scoop, created-at-3u, solid, shelled+tab,
  4 equivalence cases, parameters-off regression, gfb1/gfb2 prefixes).
- 2026-10-11 — Removed the "Store settings as user parameters" checkbox at Dave's request:
  parameters are always created. Dropped the parameters-off test case (11 checks remain).

## Current state / next step

Demo-able: create a bin with the dialog, then Modify > Change Parameters > `gfb1_bin_height_u`
5 → 3 (or `gfb1_height_unit`). Not yet verified by hand: the dialog itself (saved
defaults) and that preview ("Update preview once") does not leave extra `gfbN_` parameters behind.

Next step: M2 — footprint scalars (`base_width`, `base_length`, `xy_clearance`, `wall_thickness`).
These go through sketch dimensions (`sketchUtils.createRectangle` needs `applyExpression` on its
4 dimensions with a `DimPoint` start point) and `cutBaseClearance`/base pattern spacing.
