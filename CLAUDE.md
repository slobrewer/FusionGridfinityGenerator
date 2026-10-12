# FusionGridfinityGenerator — fork notes for Claude Code

Fork of Le0Michine/FusionGridfinityGenerator (remote `upstream`); Dave's fork is `origin`
(slobrewer). Work happens on stacked branches, one per milestone, each with a PR on the fork
(never upstream): `parametric-user-parameters` (M0+M1, PR #1 → `master`) ← `parametric-m2` ←
`parametric-m3` ← … Each PR's base is the previous milestone's branch.

**Current project:** make the bin dialog's choices live as Fusion user parameters that drive the
model. Plan: `docs/PARAMETRIC_PLAN.md`. Progress log (update after every milestone/session):
`docs/PARAMETRIC_PROGRESS.md`.

## Running / testing locally

- Pure-Python Fusion add-in, no build step. Fusion's bundled Python is 3.14 (macOS).
- The add-in is named **GridfinityGeneratorParametric** (entry file, manifest and the symlink name
  must all match — Fusion requires it), manifest version 2.0.0.0. The repo is symlinked into
  Fusion's add-in folder:
  `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/GridfinityGeneratorParametric → ~/Developer/FusionGridfinityGenerator`
- The **App Store build (1.4.3.0) is also installed** at
  `~/Library/Application Support/Autodesk/ApplicationPlugins/GridfinityGenerator.bundle` and
  runs on startup. The fork uses its own manifest GUID, `config.ADDIN_NAME =
  'GridfinityGeneratorParametric'` (which prefixes every command id), renamed entry
  file/manifest and "(parametric)" command labels, so both can run side by side. Keep those
  differences when merging from upstream (upstream renames of `GridfinityGenerator.py`/`.manifest`
  will need manual resolution).
- After editing code: Stop + Run the add-in in the Scripts and Add-Ins dialog. Fusion caches
  imported submodules; if a change does not show up, restart Fusion.
- `config.DEBUG = True` → `futil.log` output goes to the *Text Commands* window (View → Show Text Commands).
- The `fusion` MCP (`mcp__fusion__fusion_mcp_execute`, `featureType: script`) runs Python inside the
  live Fusion session — use it to verify API behaviour and to run the in-Fusion assertion
  scripts in `tests/fusion/`. Create a new document in the script (`app.documents.add(...)`) rather
  than touching whatever Dave has open; close scratch docs with `doc.close(False)`.

## Fusion API gotchas (verified 2026-10-11)

- API lengths are **cm**; `ValueInput.createByReal(5)` = 5 cm but `createByString('5')` = 5 **mm**
  (design default units). Expressions must always carry units.
- Expression function arguments use **semicolons**: `max(a; b)`, `min(a; b)`.
- `sketchDimension.parameter.expression = '...'` works after the dimension is created.
- Patterning **bodies** and combining later does not survive a quantity change; patterning
  **features** (incl. Combine) does. See plan §1.
- Timeline must be on (design history); the add-in refuses Direct Design.
- Timeline groups report `healthState == 5` with no message; check group members for health.
- Tests: `python3 -m unittest discover -s tests` (plain Python) and
  `tests/fusion/bin_parameters_test.py` run via the fusion MCP with
  `runpy.run_path(...)['runSuite'](['footprint'])` (named groups) or `['run'](ctx)` (everything)
  — see `docs/PARAMETRIC_PROGRESS.md`. Every new live parameter gets a case there, including an
  edited-vs-fresh equivalence check (volume + face count + bounding box; the edit must also
  change the model, so a parameter that drives nothing fails).
- How the parametric path works: generator inputs become `Dim` objects (`lib/gridfinityUtils/dim.py`)
  that carry value + expression; utilities call `toValueInput()` / `applyExpression()`; points that
  may hold Dims are `DimPoint`s (`asPoint3D()` where Fusion needs a Point3D). Use `dmax`/`dmin`,
  never builtin `max`/`min`, on values that may be Dims.
- Sketch frames (verified 2026-10-11): a sketch on an offset origin plane or on a planar face has its
  origin at the projected model origin and axes along +/- model axes — XY/top face: (+X, +Y);
  bottom face: (-X, +Y); YZ plane: (x = -Z, y = +Y); XZ plane: (x = +X, y = -Z). That is what lets
  `sketchUtils.modelToSketch()` turn a `DimPoint` into sketch coordinates that keep expressions.
  Sketch distance dimensions are unsigned; `applyExpression()` links negative coordinates by `abs`.
- `MoveFeatureInput.defineAsRotate(axis, angle)` fails with `3 : Invalid entity` unless the axis is
  a proxy in the active occurrence's context (`axis.createForAssemblyContext(occurrence)`) — even
  the component's own Z axis. A free move (`defineAsFreeMove(matrix)`) is not parametric.
- In-Fusion test scripts must close their scratch documents in a `finally` (the harness tracks them
  in `CREATED_DOCUMENTS`); a crashed run once left 15 Untitled documents open next to Dave's work.
- The fusion MCP call times out after a few minutes but the script **keeps running** inside Fusion,
  and because the harness calls `adsk.doEvents()` the next MCP request runs *interleaved* with it
  (its output arrives with that later call). Run one test group per MCP call (~30 bins max), and
  after a timeout poll with a read-only script until `SUMMARY` appears — never run cleanup while
  a timed-out run is still going.

## Conventions

- Keep upstream's style (camelCase, `*GeneratorInput` property classes, `futil.log` logging).
- Commit per milestone; commit messages reference the milestone (`M1: ...`).
- Don't rewrite upstream's unrelated code — this fork should stay mergeable with `upstream/master`.
