# FusionGridfinityGenerator — fork notes for Claude Code

Fork of Le0Michine/FusionGridfinityGenerator (remote `upstream`); Dave's fork is `origin`
(slobrewer). Work happens on branch `parametric-user-parameters`.

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
  scripts in `docs/tests/`. Create a new document in the script (`app.documents.add(...)`) rather
  than touching whatever Dave has open; close scratch docs with `doc.close(False)`.

## Fusion API gotchas (verified 2026-10-11)

- API lengths are **cm**; `ValueInput.createByReal(5)` = 5 cm but `createByString('5')` = 5 **mm**
  (design default units). Expressions must always carry units.
- Expression function arguments use **semicolons**: `max(a; b)`, `min(a; b)`.
- `sketchDimension.parameter.expression = '...'` works after the dimension is created.
- Patterning **bodies** and combining later does not survive a quantity change; patterning
  **features** (incl. Combine) does. See plan §1.
- Timeline must be on (design history); the add-in refuses Direct Design.

## Conventions

- Keep upstream's style (camelCase, `*GeneratorInput` property classes, `futil.log` logging).
- Commit per milestone; commit messages reference the milestone (`M1: ...`).
- Don't rewrite upstream's unrelated code — this fork should stay mergeable with `upstream/master`.
