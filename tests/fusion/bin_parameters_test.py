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
        'bin_type': e.BIN_TYPE_HOLLOW, 'compartments_x': 1, 'compartments_y': 1, 'store': True,
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
        e.STORE_PARAMETERS_INPUT: value(s['store']),
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
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
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
    return (round(sum(b.volume for b in bodies), 4), sum(b.faces.count for b in bodies))

def equivalenceCase(entry, app, label, changes, finalOverrides, **overrides):
    """Create with `overrides`, apply parameter `changes`, compare against a bin created directly
    with `finalOverrides` (volume in cm^3 and face count must match)."""
    edited = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, **overrides)), executeFailed=False, executeFailedMessage='')
    entry.generateBin(args)
    for suffix, expression in changes:
        design.userParameters.itemByName('gfb1_' + suffix).expression = expression
    adsk.doEvents()
    editedShape = shape(design)
    bad = unhealthy(design)
    direct = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    merged = dict(overrides)
    merged.update(finalOverrides)
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, **merged)), executeFailed=False, executeFailedMessage='')
    entry.generateBin(args)
    directShape = shape(design)
    passed = editedShape == directShape and not bad
    print(f'[{"PASS" if passed else "FAIL"}] {label}: edited (volume, faces)={editedShape} direct={directShape} unhealthy={bad}')
    return [edited, direct], passed

def run(_context: str):
    app = adsk.core.Application.get()
    entry = loadEntry()
    # total height = bin_height_u * height_unit + lip (4.4 mm lip minus 0.6 mm top recess) when height_unit >= 5 mm base height
    heightSteps = [('bin_height_u', '3', 21 + 3.8), ('bin_height_u', '7', 49 + 3.8), ('height_unit', '10 mm', 70 + 3.8), ('bin_height_u', '5', 50 + 3.8)]
    cases = [
        ('default 2x3x5 hollow with lip', heightSteps, {}),
        ('scoop + tab + notches + 2x2 compartments + magnets + screws', heightSteps,
         dict(scoop=True, tab=True, lip_notches=True, compartments_x=2, compartments_y=2, magnets=True, screw_holes=True, magnet_tabs=True)),
        ('no lip, scoop', [('bin_height_u', '3', 21), ('bin_height_u', '6', 42)], dict(lip=False, scoop=True)),
        ('scoop + tab created at 3u', [('bin_height_u', '6', 42 + 3.8), ('bin_height_u', '2', 14 + 3.8), ('bin_height_u', '3', 21 + 3.8)],
         dict(height_u=3, scoop=True, tab=True)),
        ('solid', [('bin_height_u', '3', 21 + 3.8)], dict(bin_type=entry.BIN_TYPE_SOLID)),
        ('shelled with tab', [('bin_height_u', '3', 21 + 3.8)], dict(bin_type=entry.BIN_TYPE_SHELLED, tab=True)),
    ]
    documents = []
    results = []
    for label, steps, overrides in cases:
        document, passed = runCase(entry, app, label, steps, **overrides)
        documents.append(document)
        results.append(passed)
    equivalences = [
        ('5u -> 3u equals fresh 3u (default)', [('bin_height_u', '3')], dict(height_u=3), {}),
        ('5u -> 3u equals fresh 3u (scoop, tab, notches, 2x2, magnets)', [('bin_height_u', '3')], dict(height_u=3),
         dict(scoop=True, tab=True, lip_notches=True, compartments_x=2, compartments_y=2, magnets=True, screw_holes=True)),
        ('3u -> 6u equals fresh 6u (scoop, tab)', [('bin_height_u', '6')], dict(height_u=6), dict(height_u=3, scoop=True, tab=True)),
        ('height unit 7 -> 10 mm equals fresh 10 mm (scoop, tab)', [('height_unit', '10 mm')], dict(height_unit=1.0), dict(scoop=True, tab=True)),
    ]
    for label, changes, finalOverrides, overrides in equivalences:
        docs, passed = equivalenceCase(entry, app, label, changes, finalOverrides, **overrides)
        documents.extend(docs)
        results.append(passed)
    # parameters off: upstream behaviour, no user parameters
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry, store=False)), executeFailed=False, executeFailedMessage='')
    passed = entry.generateBin(args) and design.userParameters.count == 0 and len(allBodies(design)) == 1
    print(f'[{"PASS" if passed else "FAIL"}] parameters off: params={design.userParameters.count} bodies={len(allBodies(design))} {args.executeFailedMessage[:300]}')
    documents.append(document)
    results.append(passed)
    # second bin in the same design gets the next prefix
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry)), executeFailed=False, executeFailedMessage='')
    entry.generateBin(args)
    args = types.SimpleNamespace(command=types.SimpleNamespace(commandInputs=dialogInputs(entry)), executeFailed=False, executeFailedMessage='')
    entry.generateBin(args)
    names = [design.userParameters.item(i).name for i in range(design.userParameters.count)]
    passed = any(n.startswith('gfb1_') for n in names) and any(n.startswith('gfb2_') for n in names)
    print(f'[{"PASS" if passed else "FAIL"}] two bins get gfb1_ and gfb2_ prefixes ({len(names)} params)')
    results.append(passed)
    print(f'SUMMARY: {sum(results)}/{len(results)} passed')
    keep = documents[-1] if KEEP_LAST_DOCUMENT else None
    for document in documents:
        if document is not keep:
            document.close(False)
