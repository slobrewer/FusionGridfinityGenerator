# In-Fusion regression test for parametric bins. Not runnable with plain Python.
# Run through the fusion MCP (mcp__fusion__fusion_mcp_execute, featureType "script") by passing
# this file's contents; it opens scratch documents, drives the real generateBin() with stub
# dialog inputs, changes user parameters and checks the model regenerates healthily.
# Scratch documents are closed at the end unless KEEP_LAST_DOCUMENT is True.
import sys
import importlib
import types
import adsk.core, adsk.fusion

REPO_PARENT = '/Users/dlouw/Developer'
PACKAGE = 'FusionGridfinityGenerator'
KEEP_LAST_DOCUMENT = False

def loadEntry():
    for name in list(sys.modules):
        if name == PACKAGE or name.startswith(PACKAGE + '.'):
            del sys.modules[name]
    if REPO_PARENT not in sys.path:
        sys.path.insert(0, REPO_PARENT)
    return importlib.import_module(PACKAGE + '.commands.commandCreateBin.entry')

# every scratch document the run opens, so they can all be closed even when a case crashes
CREATED_DOCUMENTS = []

def newDocument(app):
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    CREATED_DOCUMENTS.append(document)
    return document

def closeCreatedDocuments(keep=None):
    for document in CREATED_DOCUMENTS:
        if document is not keep and document.isValid:
            document.close(False)
    CREATED_DOCUMENTS.clear()

def value(v):
    return types.SimpleNamespace(value=v)

def dropdown(name):
    return types.SimpleNamespace(selectedItem=types.SimpleNamespace(name=name))

class FakeInputs:
    def __init__(self, items):
        self.items = items
    def itemById(self, inputId):
        return self.items[inputId]

def dialogInputs(e, **overrides):
    settings = {
        'base_width': 4.2, 'base_length': 4.2, 'height_unit': 0.7, 'xy_clearance': 0.025,
        'width_u': 2, 'length_u': 3, 'height_u': 5, 'wall': 0.12,
        'generate_base': True, 'generate_body': True, 'screw_holes': False, 'magnets': False,
        'magnet_tabs': False, 'screw_diameter': 0.3, 'magnet_diameter': 0.65, 'magnet_depth': 0.24,
        'lip': True, 'lip_notches': False, 'scoop': False, 'scoop_radius': 2.5,
        'tab': False, 'tab_length': 1, 'tab_width': 1.3, 'tab_position': 0, 'tab_angle': 0.7853981633974483,
        'bin_type': e.BIN_TYPE_HOLLOW, 'compartments_x': 1, 'compartments_y': 1,
    }
    settings.update(overrides)
    s = settings
    items = {
        e.BIN_BASE_WIDTH_UNIT_INPUT_ID: value(s['base_width']),
        e.BIN_BASE_LENGTH_UNIT_INPUT_ID: value(s['base_length']),
        e.BIN_HEIGHT_UNIT_INPUT_ID: value(s['height_unit']),
        e.BIN_XY_CLEARANCE_INPUT_ID: value(s['xy_clearance']),
        e.BIN_WIDTH_INPUT_ID: value(s['width_u']),
        e.BIN_LENGTH_INPUT_ID: value(s['length_u']),
        e.BIN_HEIGHT_INPUT_ID: value(s['height_u']),
        e.BIN_WALL_THICKNESS_INPUT_ID: value(s['wall']),
        e.BIN_SCREW_HOLES_INPUT_ID: value(s['screw_holes']),
        e.BIN_GENERATE_BASE_INPUT_ID: value(s['generate_base']),
        e.BIN_GENERATE_BODY_INPUT_ID: value(s['generate_body']),
        e.BIN_MAGNET_CUTOUTS_INPUT_ID: value(s['magnets']),
        e.BIN_SCREW_DIAMETER_INPUT: value(s['screw_diameter']),
        e.BIN_MAGNET_CUTOUTS_TABS_INPUT_ID: value(s['magnet_tabs']),
        e.BIN_MAGNET_DIAMETER_INPUT: value(s['magnet_diameter']),
        e.BIN_MAGNET_HEIGHT_INPUT: value(s['magnet_depth']),
        e.BIN_WITH_LIP_INPUT_ID: value(s['lip']),
        e.BIN_WITH_LIP_NOTCHES_INPUT_ID: value(s['lip_notches']),
        e.BIN_HAS_SCOOP_INPUT_ID: value(s['scoop']),
        e.BIN_SCOOP_MAX_RADIUS_INPUT_ID: value(s['scoop_radius']),
        e.BIN_HAS_TAB_INPUT_ID: value(s['tab']),
        e.BIN_TAB_LENGTH_INPUT_ID: value(s['tab_length']),
        e.BIN_TAB_WIDTH_INPUT_ID: value(s['tab_width']),
        e.BIN_TAB_POSITION_INPUT_ID: value(s['tab_position']),
        e.BIN_TAB_ANGLE_INPUT_ID: value(s['tab_angle']),
        e.BIN_TYPE_DROPDOWN_ID: dropdown(s['bin_type']),
        e.BIN_COMPARTMENTS_GRID_TYPE_ID: dropdown(e.BIN_COMPARTMENTS_GRID_TYPE_UNIFORM),
        e.BIN_COMPARTMENTS_TABLE_ID: types.SimpleNamespace(rowCount=1),
        e.BIN_COMPARTMENTS_GRID_BASE_WIDTH_ID: value(s['compartments_x']),
        e.BIN_COMPARTMENTS_GRID_BASE_LENGTH_ID: value(s['compartments_y']),
    }
    return FakeInputs(items)

def unhealthy(design):
    # timeline groups have no health of their own (they report state 5), so check their members
    items = []
    for i in range(design.timeline.count):
        item = design.timeline.item(i)
        if item.isGroup:
            group = adsk.fusion.TimelineGroup.cast(item)
            items.extend(group.item(j) for j in range(group.count))
        else:
            items.append(item)
    return [f'{item.name}: {item.errorOrWarningMessage[:120]}' for item in items
            if item.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState]

def allBodies(design):
    return [body for component in design.allComponents for body in component.bRepBodies if body.isVisible]

def heightMm(design):
    bodies = allBodies(design)
    top = max(b.boundingBox.maxPoint.z for b in bodies)
    bottom = min(b.boundingBox.minPoint.z for b in bodies)
    return round((top - bottom) * 10, 3)

def footprintMm(design):
    bodies = allBodies(design)
    return (round((max(b.boundingBox.maxPoint.x for b in bodies) - min(b.boundingBox.minPoint.x for b in bodies)) * 10, 3),
            round((max(b.boundingBox.maxPoint.y for b in bodies) - min(b.boundingBox.minPoint.y for b in bodies)) * 10, 3))

def runCase(entry, app, label, steps, **overrides):
    """steps: list of (parameter suffix, expression, expected total height mm or None)."""
    document = newDocument(app)
    design = adsk.fusion.Design.cast(app.activeProduct)
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, **overrides)),
                                 executeFailed=False, executeFailedMessage='')
    ok = entry.generateBin(args)
    failures = []
    if not ok:
        failures.append('generateBin failed: ' + str(args.executeFailedMessage)[:600])
        print(f'[FAIL] {label}: ' + '; '.join(failures))
        return document, False
    parameterNames = [design.userParameters.item(i).name for i in range(design.userParameters.count)]
    print(f'{label}: created, bodies={len(allBodies(design))} height={heightMm(design)}mm footprint={footprintMm(design)} params={len(parameterNames)}')
    if len(allBodies(design)) != 1:
        failures.append(f'expected 1 body after create, got {len(allBodies(design))}')
    for suffix, expression, expectedHeight in steps:
        parameter = design.userParameters.itemByName('gfb1_' + suffix)
        if parameter is None:
            failures.append(f'missing parameter gfb1_{suffix}')
            continue
        parameter.expression = expression
        adsk.doEvents()
        bad = unhealthy(design)
        height = heightMm(design)
        bodies = len(allBodies(design))
        print(f'  gfb1_{suffix} = {expression}: height={height}mm bodies={bodies} unhealthy={bad}')
        if bad:
            failures.append(f'unhealthy after {suffix}={expression}: {bad}')
        if bodies != 1:
            failures.append(f'{bodies} bodies after {suffix}={expression}')
        if expectedHeight is not None and abs(height - expectedHeight) > 0.01:
            failures.append(f'height {height} != expected {expectedHeight} after {suffix}={expression}')
    print(f'[{"FAIL" if failures else "PASS"}] {label}' + ('' if not failures else ': ' + '; '.join(failures)))
    return document, not failures

def shape(design):
    bodies = allBodies(design)
    if not bodies:
        return (0, 0, ())
    box = tuple(round(v * 10, 3) for v in (
        min(b.boundingBox.minPoint.x for b in bodies), min(b.boundingBox.minPoint.y for b in bodies), min(b.boundingBox.minPoint.z for b in bodies),
        max(b.boundingBox.maxPoint.x for b in bodies), max(b.boundingBox.maxPoint.y for b in bodies), max(b.boundingBox.maxPoint.z for b in bodies)))
    return (round(sum(b.volume for b in bodies), 4), sum(b.faces.count for b in bodies), box)

def equivalenceCase(entry, app, label, changes, finalOverrides, **overrides):
    """Create with `overrides`, apply parameter `changes`, compare against a bin created directly
    with `finalOverrides` (volume in cm^3 and face count must match)."""
    edited = newDocument(app)
    design = adsk.fusion.Design.cast(app.activeProduct)
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, **overrides)), executeFailed=False, executeFailedMessage='')
    createdOk = entry.generateBin(args)
    originalShape = shape(design)
    for suffix, expression in changes:
        design.userParameters.itemByName('gfb1_' + suffix).expression = expression
    adsk.doEvents()
    editedShape = shape(design)
    bad = unhealthy(design)
    direct = newDocument(app)
    design = adsk.fusion.Design.cast(app.activeProduct)
    merged = dict(overrides)
    merged.update(finalOverrides)
    args2 = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, **merged)), executeFailed=False, executeFailedMessage='')
    directOk = entry.generateBin(args2)
    directShape = shape(design)
    # the edit has to change the model (else the parameter drives nothing) and match a fresh build
    changed = editedShape != originalShape
    passed = createdOk and directOk and changed and editedShape == directShape and not bad
    detail = '' if createdOk and directOk else f' generate failed: {args.executeFailedMessage[:300]} {args2.executeFailedMessage[:300]}'
    print(f'[{"PASS" if passed else "FAIL"}] {label}: edited (volume, faces, box)={editedShape} direct={directShape} changed={changed} unhealthy={bad}{detail}')
    return [edited, direct], passed


# feature mixes the equivalence checks run against
FULL = dict(scoop=True, tab=True, lip_notches=True, compartments_x=2, compartments_y=2, magnets=True, screw_holes=True, magnet_tabs=True)
SCOOP_TAB = dict(scoop=True, tab=True)

def heightGroup(entry, app):
    results = []
    # total height = bin_height_u * height_unit + lip (4.4 mm lip minus 0.6 mm top recess) when height_unit >= 5 mm base height
    heightSteps = [('bin_height_u', '3', 21 + 3.8), ('bin_height_u', '7', 49 + 3.8), ('height_unit', '10 mm', 70 + 3.8), ('bin_height_u', '5', 50 + 3.8)]
    cases = [
        ('default 2x3x5 hollow with lip', heightSteps, {}),
        ('scoop + tab + notches + 2x2 compartments + magnets + screws', heightSteps, FULL),
        ('no lip, scoop', [('bin_height_u', '3', 21), ('bin_height_u', '6', 42)], dict(lip=False, scoop=True)),
        ('scoop + tab created at 3u', [('bin_height_u', '6', 42 + 3.8), ('bin_height_u', '2', 14 + 3.8), ('bin_height_u', '3', 21 + 3.8)],
         dict(height_u=3, scoop=True, tab=True)),
        ('solid', [('bin_height_u', '3', 21 + 3.8)], dict(bin_type=entry.BIN_TYPE_SOLID)),
        ('shelled with tab', [('bin_height_u', '3', 21 + 3.8)], dict(bin_type=entry.BIN_TYPE_SHELLED, tab=True)),
    ]
    for label, steps, overrides in cases:
        results.append(runCase(entry, app, label, steps, **overrides)[1])
    equivalences = [
        ('5u -> 3u equals fresh 3u (default)', [('bin_height_u', '3')], dict(height_u=3), {}),
        ('5u -> 3u equals fresh 3u (full)', [('bin_height_u', '3')], dict(height_u=3), FULL),
        ('3u -> 6u equals fresh 6u (scoop, tab)', [('bin_height_u', '6')], dict(height_u=6), dict(height_u=3, scoop=True, tab=True)),
        ('height unit 7 -> 10 mm equals fresh 10 mm (scoop, tab)', [('height_unit', '10 mm')], dict(height_unit=1.0), SCOOP_TAB),
    ]
    for label, changes, finalOverrides, overrides in equivalences:
        results.append(equivalenceCase(entry, app, label, changes, finalOverrides, **overrides)[1])
    return results

def footprintGroup(entry, app):
    """M2: base unit size, xy clearance, wall thickness."""
    results = []
    mixes = [
        ('full', FULL),
        ('shelled + tab', dict(bin_type=entry.BIN_TYPE_SHELLED, tab=True)),
        ('solid', dict(bin_type=entry.BIN_TYPE_SOLID)),
        ('no lip, scoop', dict(lip=False, scoop=True)),
    ]
    changes = [
        ('base 42 -> 40 x 45 mm', [('base_width', '40 mm'), ('base_length', '45 mm')], dict(base_width=4.0, base_length=4.5)),
        ('wall 1.2 -> 1.6 mm', [('wall_thickness', '1.6 mm')], dict(wall=0.16)),
        ('wall 1.2 -> 0.8 mm', [('wall_thickness', '0.8 mm')], dict(wall=0.08)),
        ('xy clearance 0.25 -> 0.5 mm', [('xy_clearance', '0.5 mm')], dict(xy_clearance=0.05)),
    ]
    for mixName, overrides in mixes:
        for changeName, parameterChanges, finalOverrides in changes:
            results.append(equivalenceCase(entry, app, f'{changeName} ({mixName})', parameterChanges, finalOverrides, **overrides)[1])
    return results

def featuresGroup(entry, app):
    """M3: screw / magnet sizes, scoop radius, label tab length / width / offset / angle."""
    results = []
    shelledTab = dict(bin_type=entry.BIN_TYPE_SHELLED, tab=True)
    checks = [
        ('magnet 6.5 -> 6 mm, depth 2.4 -> 2 mm (full)', [('magnet_diameter', '6 mm'), ('magnet_depth', '2 mm')],
         dict(magnet_diameter=0.6, magnet_depth=0.2), FULL),
        ('magnet depth 2.4 -> 2.8 mm, no tabs (magnets + screws)', [('magnet_depth', '2.8 mm')],
         dict(magnet_depth=0.28), dict(magnets=True, screw_holes=True)),
        ('screw 3 -> 2.5 mm (full)', [('screw_diameter', '2.5 mm')], dict(screw_diameter=0.25), FULL),
        ('scoop radius 25 -> 15 mm (scoop + tab)', [('scoop_radius', '15 mm')], dict(scoop_radius=1.5), SCOOP_TAB),
        ('scoop radius 25 -> 10 mm (no lip, scoop)', [('scoop_radius', '10 mm')], dict(scoop_radius=1.0), dict(lip=False, scoop=True)),
        ('tab angle 45 -> 60 deg (scoop + tab)', [('tab_angle', '60 deg')], dict(tab_angle=1.0471975511965976), SCOOP_TAB),
        ('tab angle 45 -> 35 deg (shelled + tab)', [('tab_angle', '35 deg')], dict(tab_angle=0.6108652381980153), shelledTab),
        ('tab width 13 -> 10 mm (full)', [('tab_width', '10 mm')], dict(tab_width=1.0), FULL),
        ('tab length 1u -> 2u (scoop + tab)', [('tab_length_u', '2')], dict(tab_length=2), SCOOP_TAB),
        ('tab offset 0 -> 1u (scoop + tab)', [('tab_offset_u', '1')], dict(tab_position=1), SCOOP_TAB),
        ('tab offset 0 -> 1u, length 1u -> 0.5u (shelled + tab)', [('tab_offset_u', '1'), ('tab_length_u', '0.5')],
         dict(tab_position=1, tab_length=0.5), shelledTab),
    ]
    for label, changes, finalOverrides, overrides in checks:
        results.append(equivalenceCase(entry, app, label, changes, finalOverrides, **overrides)[1])
    return results

def prefixGroup(entry, app):
    newDocument(app)
    design = adsk.fusion.Design.cast(app.activeProduct)
    for _ in range(2):
        args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry)), executeFailed=False, executeFailedMessage='')
        entry.generateBin(args)
    names = [design.userParameters.item(i).name for i in range(design.userParameters.count)]
    passed = any(n.startswith('gfb1_') for n in names) and any(n.startswith('gfb2_') for n in names)
    print(f'[{"PASS" if passed else "FAIL"}] two bins get gfb1_ and gfb2_ prefixes ({len(names)} params)')
    return [passed]

def findUpstreamEntry():
    """The App Store build of the add-in (upstream code) when it is loaded in this Fusion session."""
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', '') or ''
        if 'ApplicationPlugins/GridfinityGenerator.bundle' in path and path.endswith('commandCreateBin/entry.py'):
            return module
    return None

def upstreamGroup(entry, app):
    """A freshly created parametric bin must be identical to upstream's. Scoops are left out: when
    parametric the scoop deliberately stops 0.5 mm below the top (see PARAMETRIC_PROGRESS.md)."""
    upstream = findUpstreamEntry()
    if upstream is None:
        print('[SKIP] upstream comparison: App Store build not loaded')
        return []
    results = []
    mixes = [
        ('default', {}),
        ('tab, notches, 2x2, magnets + tabs, screws', dict(FULL, scoop=False)),
        ('shelled + tab', dict(bin_type=entry.BIN_TYPE_SHELLED, tab=True)),
        ('solid', dict(bin_type=entry.BIN_TYPE_SOLID)),
        ('no lip, 40 x 45 base, wall 1.6, xy 0.5', dict(lip=False, base_width=4.0, base_length=4.5, wall=0.16, xy_clearance=0.05)),
    ]
    for label, overrides in mixes:
        shapes = []
        for module in (entry, upstream):
            newDocument(app)
            design = adsk.fusion.Design.cast(app.activeProduct)
            args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, **overrides)), executeFailed=False, executeFailedMessage='')
            ok = module.generateBin(args)
            shapes.append((shape(design), ok, args.executeFailedMessage[:300], unhealthy(design)))
        (forkShape, forkOk, forkMessage, forkBad), (upstreamShape, upstreamOk, upstreamMessage, _) = shapes
        passed = forkOk and upstreamOk and forkShape == upstreamShape and not forkBad
        detail = '' if forkOk and upstreamOk else f' failed: {forkMessage} {upstreamMessage}'
        print(f'[{"PASS" if passed else "FAIL"}] {label} same as upstream: fork={forkShape} upstream={upstreamShape} unhealthy={forkBad}{detail}')
        results.append(passed)
    return results

GROUPS = {
    'upstream': upstreamGroup,
    'height': heightGroup,
    'footprint': footprintGroup,
    'features': featuresGroup,
    'prefix': prefixGroup,
}

def runSuite(groups=None):
    """Run the named groups (all when None). Scratch documents are always closed afterwards."""
    app = adsk.core.Application.get()
    entry = loadEntry()
    results = []
    try:
        for name, group in GROUPS.items():
            if groups is None or name in groups:
                print(f'== {name}')
                results.extend(group(entry, app))
    finally:
        keep = CREATED_DOCUMENTS[-1] if KEEP_LAST_DOCUMENT and CREATED_DOCUMENTS else None
        closeCreatedDocuments(keep)
    print(f'SUMMARY: {sum(results)}/{len(results)} passed')
    return results

def run(_context: str):
    runSuite()
