# Parametric user-parameters refactor — plan

Goal: every numeric choice in the *Gridfinity bin* dialog is written to the design as a named
**user parameter**, and the generated features reference those parameters by **expression**, so
changing e.g. `gfb1_bin_height_u` from 5 to 3 in *Modify → Change Parameters* regenerates the bin.

Upstream asked for exactly this in issues #49 and #50 and never shipped it. The author's stated
blocker — user parameters are design-global, not per-component — is solved here with a per-bin
name prefix.

Status / progress log: `docs/PARAMETRIC_PROGRESS.md` (keep it current after every milestone).

---

## 1. What the live Fusion tests established (2026-10-11, Fusion 2705.1.30, macOS)

All verified by running scripts inside Fusion via the `fusion` MCP (`mcp__fusion__fusion_mcp_execute`,
`featureType: script`). Re-run them if Fusion is updated.

| # | Fact | Consequence |
|---|---|---|
| 1 | `design.userParameters.add(name, ValueInput.createByString('42 mm'), 'mm', comment)` works; unitless params use unit `''`. Angle params use `'deg'`. | Parameter creation is straightforward. |
| 2 | Function args are **semicolon**-separated: `max(0 mm; x - 4.75 mm)` OK, `max(a, b)` → *Invalid expression*. `min`, `floor` work. | Every `max()/min()` in the generators must emit `;`. |
| 3 | A unitless string in a length context is **mm** (`createByString('5')` → 5 mm) whereas `createByReal(5)` is **5 cm** (API internal units). | Expressions must always carry units (`'7 mm'`) or reference unit-bearing params. Never emit a bare float into a length expression. |
| 4 | `sketchDimension.parameter.expression = '...'` can be set *after* `addDistanceDimension(...)`; the geometry does not move as long as the expression evaluates to the current value. | Keep building sketches from literal `Point3D`s (so face/edge selection code is untouched), then stamp expressions onto the dimensions. |
| 5 | `createByString` works for extrude distance, fillet radius, chamfer distance, construction-plane offset, pattern quantity and spacing. Expressions are preserved on the ModelParameter (`extentOne.distance.expression`). | Feature dimensions become parametric with a one-line change each. |
| 6 | Changing `bin_height_u` 5→3 and `bin_width_u` 2→3 after creation regenerated the body; a fillet whose edges were selected by length at creation stayed healthy. | Topology naming survives scalar changes — the "easy" milestones are safe. |
| 7 | **Body patterns do not re-merge**: pattern of *bodies* + later Combine/Join (explicit or default participants) leaves new instances as stray bodies when quantity grows and gives *reference lost* warnings when it shrinks. | The existing base pattern (`createBaseBodyPattern` + `combineFeatures`) cannot be made count-parametric as-is. |
| 8 | **Feature patterns do re-merge**: `rectangularPatternFeatures` over a chain of *features* (join-extrude, fillet, chamfer, cut-extrude, circular pattern, **and Combine**) with `quantityOne = 'n'` regenerated as a single healthy body for n = 2 → 3 → 1. | Bin X/Y count is doable (Milestone 4) by patterning the base *features* instead of the base *body*. |

---

## 2. Architecture

### 2.1 `Dim` — a number that remembers its expression

New module `lib/gridfinityUtils/dim.py`:

```python
class Dim:
    """A length/count/angle that carries both its numeric API value (cm / unitless / rad)
    and the Fusion expression string that produces it."""
    value: float      # what the current code already uses (cm)
    expr: str         # e.g. '(gfb1_base_width * gfb1_bin_width_u) - gfb1_xy_clearance * 2'
```

- Operators `+ - * /`, unary `-`, and `Dim.max(a, b)` / `Dim.min(a, b)` return a new `Dim` with
  both fields computed; expressions are parenthesised conservatively; `max/min` emit `;`.
- `float(dim)`, `<`, `>` etc. use `.value`, so `math.tan(dim)`, `min(...)` comparisons and the
  existing `if input.wallThickness < const.BIN_LIP_WALL_THICKNESS:` style code keep working.
- Constructors: `Dim.mm(2.4)` → `value=0.24, expr='2.4 mm'`; `Dim.unitless(2)`; `Dim.deg(45)`;
  `Dim.param(userParameter)` → `value=p.value, expr=p.name`.
- `Dim.of(x)` wraps a plain float as a literal (`'{x*10} mm'`) so unconverted call sites keep working during the migration.
- `toValueInput(x: float | Dim)` → `createByString(x.expr)` or `createByReal(x)`.
- `applyExpression(sketchDimension, x)` → sets `.parameter.expression` when `x` is a `Dim`, no-op for floats.
- `DimPoint(x, y, z)` with `.toPoint3D()` for the origin-point plumbing (`geometryUtils.createOffsetPoint` etc.).

This is the whole trick: once the *inputs* to the generators are `Dim`s, the existing arithmetic
(`actualBodyWidth = (input.baseWidth * input.binWidth) - input.xyClearance * 2.0`) produces
correct expressions for free. The diff in the generators is then mostly
`createByReal(h)` → `toValueInput(h)` plus `applyExpression(...)` after each sketch dimension.

Sign gotcha: a sketch distance dimension is always positive and the direction is fixed by the
initial geometry. Expressions stamped onto dimensions must evaluate positive (e.g. the base origin
at `-xyClearance` gets expression `gfb1_xy_clearance`, not `-gfb1_xy_clearance`). Extrude distances
can be negative (`'-3 mm'` works).

### 2.2 `BinParameters` — creating and naming the user parameters

New module `lib/gridfinityUtils/binParameters.py`:

- `prefix = f'gfb{N}_'` where `N` = smallest positive integer such that no existing user parameter
  starts with `gfb{N}_` (scan `design.userParameters`). Prefix is also embedded in the component
  / timeline-group name (`Gridfinity bin 3x2x5 [gfb1]`) so the mapping is visible in the browser.
- Each parameter: `comment = 'Gridfinity bin gfb1 — <dialog label>'`. Fusion has no parameter
  folders; creation order + shared prefix + shared comment is the "grouping". (Tip for users:
  the Parameters dialog filter box matches on name, so typing `gfb1_` shows just that bin.)
- `BinParameters.create(design, ui_values) -> BinParameters` adds the params and exposes each as a
  `Dim` attribute. Idempotent: if a param with that name already exists (preview re-runs), update
  its expression instead of failing. Preview (`executePreview`) runs inside the command's
  transaction, so params created during preview are rolled back with it — verify in M0.
- Dialog gets one checkbox in the *Changes*/*Preview* area: **"Store settings as user parameters"**
  (default on, persisted with the other UI defaults). Off → generator receives plain floats and
  behaves exactly as upstream (keeps the upstream-merge story clean and gives a fallback).

Parameter list (bin). "Live" = geometry references it; "Info" = recorded for the record, changing
it does nothing (documented in the comment: `(informational)`).

| Name (after prefix) | Unit | Dialog input | Live from |
|---|---|---|---|
| `base_width` | mm | Base width unit | M2 |
| `base_length` | mm | Base length unit | M2 |
| `height_unit` | mm | Bin height unit | M1 |
| `xy_clearance` | mm | Bin xy clearance | M2 |
| `bin_width_u` | – | Bin width X (u) | M4 (Info until then) |
| `bin_length_u` | – | Bin length Y (u) | M4 (Info until then) |
| `bin_height_u` | – | Bin height Z (u) | M1 |
| `wall_thickness` | mm | Bin wall thickness | M2 |
| `screw_diameter` | mm | Screw hole diameter | M3 |
| `magnet_diameter` | mm | Magnet cutout diameter | M3 |
| `magnet_depth` | mm | Magnet cutout depth | M3 |
| `scoop_radius` | mm | Scoop max radius | M3 |
| `tab_length_u` | – | Tab length (u) | M3 |
| `tab_width` | mm | Tab width | M3 |
| `tab_offset_u` | – | Tab offset (u) | M3 |
| `tab_angle` | deg | Tab overhang angle | M3 |
| `compartments_x`, `compartments_y` | – | Grid width/length | Info (changing count adds/removes cutouts — out of scope) |
| `has_lip`, `has_lip_notches`, `has_scoop`, `has_tab`, `has_screw_holes`, `has_magnets`, `has_magnet_tabs`, `bin_type` (0 hollow/1 shelled/2 solid), `generate_base`, `generate_body` | – | checkboxes/dropdowns | Info (0/1) — these choose code branches |

Gridfinity spec constants (`const.py`: base section heights, lip height, etc.) stay literal
(`Dim.mm(...)`) in expressions. Optionally (M5+) promote them to shared `gf_*` params.

### 2.3 Threading `Dim` through the generators

`BaseGeneratorInput`, `BinBodyGeneratorInput`, `BinBodyLipGeneratorInput`,
`BinBodyCutoutGeneratorInput`, `BinBodyTabGeneratorInput` keep their property names; the types
widen to `float | Dim`. `originPoint`/`origin` gain a `DimPoint` sibling (or become `DimPoint`
with `.toPoint3D()` at the call sites that need a `Point3D`).

Utility functions that take a distance (`extrudeUtils.*`, `shapeUtils.*`, `filletUtils.*`,
`sketchUtils.createRectangle`, `baseGenerator.createCircleAtPointSketch`, construction-plane
offsets) accept `float | Dim`, call `toValueInput` for feature inputs and `applyExpression` for the
sketch dimensions they create. `createRectangle` stamps 4 expressions: origin-X, origin-Y, width,
length (`startPoint` must therefore come in as a `DimPoint`).

---

## 3. Milestones

Each milestone ends with a manual demo in Fusion plus (where practical) an MCP script that
asserts the result (`docs/tests/` — see §4). Commit per milestone on branch
`parametric-user-parameters`.

### M0 — Scaffolding (no geometry change)
1. `dim.py` with unit tests runnable in plain Python (`python3 -m pytest docs/tests/test_dim.py`;
   `Dim` has no `adsk` dependency — keep `toValueInput` in a separate thin module or import lazily).
2. `binParameters.py`: prefix allocation, idempotent create, comments, the checkbox in the dialog,
   persisted default.
3. `generateBin` creates all parameters (all Info at this point) and names the component/timeline
   group with the prefix.
4. Verify preview rollback does not leak parameters; verify two bins in one design get `gfb1_`/`gfb2_`.

**Demo:** create a bin → *Change Parameters* shows the `gfb1_*` group with correct values and comments.

### M1 — Height chain (`bin_height_u`, `height_unit`)
Wire the Z dimension end-to-end in `binBodyGenerator.createGridfinityBinBody`:
`binBodyTotalHeight = (bin_height_u - 1) * height_unit + max(0 mm; height_unit - 4.75 mm)` →
body extrude distance; corner-fillet edge filter (numeric only — fine); lip origin plane offset;
compartment cutout plane offset and depth (`min(total - 1 mm; depth)`); tab origin Z; compartment top
clearance cutout. Also the `Depth (mm)` column of the custom-compartments table becomes
`min(binBodyTotalHeight - 1 mm; <literal>)`.

**Demo:** 2x3x5 hollow bin with lip, scoop and tab → set `gfb1_bin_height_u = 3` → bin shortens, lip,
scoop and tab ride along, timeline all green. Then `height_unit = 10 mm`.

### M2 — Footprint scalars (`base_width`, `base_length`, `xy_clearance`, `wall_thickness`)
Body/lip rectangle dims, `binCornerFilletRadius = 4 mm - xy_clearance`, wall offsets of the
compartment cutouts and their fillet radii (`4 mm - xy - wall`), lip mid cutout, lip bottom
chamfer, `createSingleGridfinityBaseBody` rectangle + screw-hole centre offsets + mid-plane
offsets, pattern spacing (`distanceOne/Two = base_width/base_length`), `cutBaseClearance`.

**Demo:** `base_width = 40 mm` (both unit sizes), `wall_thickness = 1.6 mm`, `xy_clearance = 0.5 mm`.

### M3 — Feature scalars (`screw_diameter`, `magnet_diameter`, `magnet_depth`, `tab_*`, `scoop_radius`)
`shapeUtils.simpleCylinder` diameter dims and offsets, magnet groove boxes, `createTabAtCircleEdgeSketch`,
`binBodyTabGenerator` (angular + distance dims; `actualTabWidth`/`actualTabHeight` use `tan` —
Fusion expressions support `tan()`/`atan()`; build them with `Dim` helpers), scoop fillet radius
(`min(scoop_radius; depth)` guarded by the fillet-radius floor).

**Demo:** magnet 6.5→6 mm & depth 2.4→2 mm; tab angle 45→60°; scoop radius 25→15 mm.

### M4 — Bin X/Y count (`bin_width_u`, `bin_length_u`) — the restructure
Replace body-pattern + combine with a **feature pattern** (test #8):
1. Create the bin body first (already parametric from M1–M2).
2. Build one base as features that *join into / cut from the bin body* (top-section extrude as
   `JoinFeatureOperation` from z=0 downward, fillet, chamfer, mid/bottom extrude join, chamfer,
   hole cut-extrudes + circular pattern, or keep the hole bodies and a Combine-cut — Combine is
   pattern-able).
3. `rectangularPatternFeatures` over that feature list with `quantityOne = bin_width_u`,
   `distanceOne = base_width`, same for Y; `patternComputeOption = AdjustPatternCompute`.
4. `cutBaseClearance` already uses expressions from M2.
5. Keep the old path behind the "Store settings as user parameters" checkbox = off.
Notches on the lip use the same base pattern (`binBodyLipGenerator`) → same treatment, or leave
notches Info-only in M4 and do them in M4b.

**Demo:** 2x3 bin → `bin_width_u = 3`, `bin_length_u = 2` → regenerates as one body, bases merged, all green.

### M5 — Baseplate command
Same treatment for `commandCreateBaseplate` / `baseplateGenerator.py` (prefix `gfp{N}_`). Its
grid is also a body pattern + combine → M4 technique. Scalars first, count second.

### Out of scope (explicitly)
Compartment grid counts, custom-grid layout, boolean/dropdown branches, shelled-bin split/shell
flow, an "edit existing bin" command. Record them as Info params only.

---

## 4. Testing

- **Unit:** `Dim` arithmetic/expression strings in plain pytest (no Fusion).
- **In-Fusion assertions:** scripts under `docs/tests/` runnable through the `fusion` MCP
  (`featureType: script`, function `run(_context)`). Pattern: open a new document, drive the
  generator, mutate parameters via `design.userParameters.itemByName(...).expression = ...`,
  `adsk.doEvents()`, then assert `rootComponent.bRepBodies.count`, bounding boxes, and that no
  timeline item has `healthState != HealthyFeatureHealthState`. Importing the add-in package
  from a script: `sys.path.insert(0, '/Users/dlouw/Developer')` then
  `import FusionGridfinityGenerator.lib.gridfinityUtils.binBodyGenerator` (namespace package;
  relative imports resolve). If that fights with Fusion's module cache, fall back to the manual
  demo and keep assertions to the *mutation* half (bin created by hand first).
- **Manual demo** per milestone as listed above; check *Modify → Change Parameters* and the
  timeline health colours.
