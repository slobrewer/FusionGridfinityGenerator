# Parametric refactor — progress

Plan: `PARAMETRIC_PLAN.md`. Update this file at the end of every session.

## Status

| Milestone | State | Branch / PR | Notes |
|---|---|---|---|
| M0 Scaffolding | done 2026-10-11 | `parametric-user-parameters`, PR #1 | `dim.py` + unit tests, `binParameters.py`, 29 `gfbN_*` params (always created) |
| M1 Height chain | done 2026-10-11 | `parametric-user-parameters`, PR #1 | `bin_height_u`, `height_unit` live |
| M2 Footprint scalars | done 2026-10-11 | `parametric-m2`, PR #2 | `base_width`, `base_length`, `xy_clearance`, `wall_thickness` live |
| M3 Feature scalars | not started | | |
| M4 X/Y count (feature pattern) | not started | | |
| M5 Baseplate | not started | | |

## How to test

- Unit: `python3 -m unittest discover -s tests` (repo root, plain Python).
- In Fusion: run through the fusion MCP (`mcp__fusion__fusion_mcp_execute`, `featureType: script`):
  ```python
  import runpy
  def run(_context: str):
      runpy.run_path('/Users/dlouw/Developer/FusionGridfinityGenerator/tests/fusion/bin_parameters_test.py')['run'](_context)
  ```
  or `['runSuite'](['footprint'])` for named groups (`height`, `footprint`, `prefix`, …).
  It imports the repo's real `generateBin()` fresh (purges cached modules), drives it with stub
  dialog inputs in scratch documents, edits parameters, and checks health, height, body count and
  **edited-vs-freshly-created equivalence (volume + face count + bounding box; the edit must
  change the model)**. Scratch docs are always closed (`finally`).
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
- Sketch frames: sketches on offset origin planes and planar faces have their origin at the
  projected model origin and axes along +/- model axes, so `sketchUtils.modelToSketch()` maps a
  `DimPoint` straight to sketch coordinates with expressions (sign flips only).
- `defineAsRotate` needs the axis as a proxy in the active occurrence (`createForAssemblyContext`),
  otherwise `3 : Invalid entity`. The magnet groove now rotates about a parametric axis through the
  hole centre instead of a fixed-point free move.
- A crashed in-Fusion run left 15 scratch documents open; the harness now tracks and closes them
  in a `finally`.
- Known limit (M2): `wall_thickness` above the lip wall (2.15 mm) does not add/remove the lip
  bottom chamfer that thinner walls get at creation time — that is a create-time branch.

## Log

- 2026-10-11 — Forked, cloned, branch `parametric-user-parameters`, symlinked into Fusion AddIns
  as `GridfinityGeneratorParametric` (own GUID / command ids, v2.0.0.0). Plan written.
- 2026-10-11 — M0 + M1 implemented and verified in Fusion: 12/12 in-Fusion checks (default,
  scoop+tab+notches+2x2+magnets+screws, no-lip scoop, created-at-3u, solid, shelled+tab,
  4 equivalence cases, parameters-off regression, gfb1/gfb2 prefixes).
- 2026-10-11 — Removed the "Store settings as user parameters" checkbox at Dave's request:
  parameters are always created. Dropped the parameters-off test case (11 checks remain).
- 2026-10-11 — Dave demoed M1 by hand in the dialog (reloaded add-in, no checkbox): height change
  via Change Parameters worked. Suite re-run after the checkbox removal: 11/11. PR #1 opened.
- 2026-10-11 — M2 implemented: `createRectangle` / `simpleCylinder` / circle sketches link their
  size and position dimensions; base and lip-notch pattern spacing, mid planes, clearance cut,
  fillet/chamfer radii and shell thickness take expressions. In Fusion: 27/27 (16 new footprint
  equivalences: base 40x45, wall 1.6 and 0.8, xy 0.5 on full / shelled+tab / solid / no-lip bins).

## Current state / next step

Demo-able: create a bin with the dialog, then Modify > Change Parameters > `gfb1_bin_height_u`,
`gfb1_height_unit`, `gfb1_base_width` / `gfb1_base_length`, `gfb1_wall_thickness`,
`gfb1_xy_clearance`. Not yet verified by hand: that preview ("Update preview once") does not
leave extra `gfbN_` parameters behind.

Next step: M3 — feature scalars (screw/magnet diameter, magnet depth, tab length/width/offset/angle,
scoop radius).
