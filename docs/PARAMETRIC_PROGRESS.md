# Parametric refactor — progress

Plan: `PARAMETRIC_PLAN.md`. Update this file at the end of every session.

## Status

| Milestone | State | Branch / PR | Notes |
|---|---|---|---|
| M0 Scaffolding | done 2026-10-11 | `parametric-user-parameters`, PR #1 | `dim.py` + unit tests, `binParameters.py`, 29 `gfbN_*` params (always created) |
| M1 Height chain | done 2026-10-11 | `parametric-user-parameters`, PR #1 | `bin_height_u`, `height_unit` live |
| M2 Footprint scalars | done 2026-10-11 | `parametric-m2`, PR #2 | `base_width`, `base_length`, `xy_clearance`, `wall_thickness` live |
| M3 Feature scalars | done 2026-10-11 | `parametric-m3`, PR #3 | screw/magnet diameter, magnet depth, scoop radius, tab length/width/offset/angle live |
| M4 X/Y count (feature pattern) | done 2026-10-11 | `parametric-m4`, PR #4 | `bin_width_u`, `bin_length_u` live (body bins); bases rebuilt as a feature pattern into a carrier |
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
- Shelled-bin label tab: upstream cut the tab with the bin and removed the leftover slivers (where
  the tab pokes out of the rounded outer corners). Which slivers exist depends on the tab position,
  so editing `tab_offset_u` + `tab_length_u` deleted the main tab instead ("tool body is lost").
  Now the tab is intersected with the bin outline inset by half the shell thickness (always one
  body) and joined; identical to upstream at creation (volume + 356 faces). A plain back-wall clip
  box is *not* enough: near the corner the outer wall dips below the inner back-wall line and a
  0.05 mm sliver survives (4 extra faces).
- Tab angle/width: `tab_width` drives the sketch's top-edge dimension through
  `width + 0.6 mm / tan((90 deg - angle) / 2)` (`dtan`), `tab_angle` the angular dimension (or its
  supplement, whichever Fusion measured). A constant length in a quotient must be `Dim.cm(...)`,
  else it is coerced unitless and Fusion reads it as mm.
- Known limit (M3): the magnet/screw groove exists only when `base height - magnet depth > 0.6 mm`
  at creation; changing `magnet_depth` across that line does not add/remove it.
- The fusion MCP times out after a few minutes but the script keeps running and interleaves with
  later calls (via `adsk.doEvents()`); one test group per call.

### M4 (bin X/Y count) — what it took

Feature patterns (`rectangularPatternFeatures` over features) follow a count change; body
patterns + Combine do not. But Fusion's feature patterns are fragile, and failures depend on the
bin size *and* the feature mix (a 5x5 full bin failed while 4x4 and 5x5-without-scoop worked), so
every rule below came from a failing case:
1. **Join the bases into a simple carrier, not the bin.** Pattern combines that target the finished
   bin body fail in some copies (`MULTIPLE_TARGET_ERROR`, a base left as a separate body). The
   bases are joined into a 0.05 mm "carrier" plate (inside the bin floor, 4 mm in from the outline)
   *before* the bin body exists; the carrier then joins the bin as one body for any count.
2. **No new bodies, fillets or chamfers inside the pattern.** Each base is three sketch extrudes
   joined straight into the carrier: top section tapered 45° (a rounded rectangle tapered by 45°
   is exactly upstream's corner fillet + 45° chamfer), straight mid section, bottom section tapered
   45°. A new body per base (even fillet/chamfer on it, then a Combine) failed when *growing* a 2x1
   bin with scoop + tab + magnets + screws ("All tool bodies are lost" — the pattern's new bodies
   apparently collide with bodies made later in the timeline); fillets/chamfers on the carrier
   failed where neighbouring bases meet (`ASM_BL_GEOM_TOO_CMPLX`).
3. **No body-to-body combines inside the pattern.** Holes are extrude-cuts into the carrier (not
   cutout bodies + Combine), repeated by a circular pattern of *features*. Cutout bodies combined
   inside nested patterns produced `IDENTICAL_TARGET_AND_TOOL_BODY` or a silently missing groove.
4. **No Move features in the pattern.** The magnet groove (cylinder ∩ boxes, rotated -45°) is now
   two sketch profiles drawn already rotated (strip clipped by the magnet circle; a diamond).
5. Fusion calls a sketch over-constrained when two points get distance dimensions of the same value
   on the same axis; `createPolygon` aligns such points with a constraint instead.
6. Lip notch cutouts are wider than their spacing — pass the spacing explicitly.
7. Clearance cut: no explicit participant bodies (the list loses its reference on count changes).
8. Scoop: also capped at `compartment length - fillet radius - 0.5 mm` (else it consumes the floor
   and the floor fillets lose their edges when the bin shrinks).
Base-only bins keep upstream's body pattern; their count parameters are marked info only.

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
  Upstream group: fresh bins identical to the App Store build; baseplate_test.py 5/5. PR #2.
- 2026-10-11 — M3 implemented: screw/magnet diameters, magnet depth, scoop radius, tab
  length/width/offset/angle. Shelled tab rebuilt as intersect-with-outline + join (see Lessons).
  In Fusion: upstream 5/5, height 10/10, footprint 16/16, features 11/11, prefix 1/1,
  baseplate 5/5.
- 2026-10-11 — M4 implemented after many Fusion pattern failures (see "M4 — what it took"):
  bases (and lip notches) as feature patterns, carrier body, tapered-extrude base, holes as cuts,
  groove drawn pre-rotated, clearance cut without participant list, scoop length cap. New test
  groups: `count` (10 edited-vs-fresh incl. 2x3→3x4/1x1, 1x1→3x2, shelled, solid, body-only) and
  `stress` (6 mixes x 6 sizes up to 6x3: create == App Store build, count edit == fresh build).

## Current state / next step

Demo-able: create a bin with the dialog, then Modify > Change Parameters > any numeric `gfb1_*`
value except the bin X/Y count: height, height unit, base size, wall, xy clearance, screw/magnet
sizes, magnet depth, scoop radius, tab length/width/offset/angle. Not yet verified by hand: that
preview ("Update preview once") does not leave extra `gfbN_` parameters behind.

Next step: M4 — bin X/Y count (`bin_width_u`, `bin_length_u`) via feature patterns.
