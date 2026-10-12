# In-Fusion regression test for the baseplate command. Not runnable with plain Python.
# Run through the fusion MCP: runpy.run_path(<this file>)['run'](_context)
# Compares baseplates from this repo against the App Store build of the add-in (upstream code,
# loaded in the same Fusion session) and closes every scratch document it opens.
import sys
import importlib
import types
import adsk.core, adsk.fusion

REPO_PARENT = '/Users/dlouw/Developer'
PACKAGE = 'FusionGridfinityGenerator'
UPSTREAM_MARKER = 'ApplicationPlugins/GridfinityGenerator.bundle'

CREATED_DOCUMENTS = []

def newDocument(app):
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    CREATED_DOCUMENTS.append(document)
    return document

def closeCreatedDocuments():
    for document in CREATED_DOCUMENTS:
        if document.isValid:
            document.close(False)
    CREATED_DOCUMENTS.clear()

def loadForkEntry():
    for name in list(sys.modules):
        if name == PACKAGE or name.startswith(PACKAGE + '.'):
            del sys.modules[name]
    if REPO_PARENT not in sys.path:
        sys.path.insert(0, REPO_PARENT)
    return importlib.import_module(PACKAGE + '.commands.commandCreateBaseplate.entry')

def findUpstreamEntry():
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', '') or ''
        if UPSTREAM_MARKER in path and path.endswith('commandCreateBaseplate/entry.py'):
            return module
    return None

def plateState(**overrides):
    state = dict(
        baseWidth=4.2, baseLength=4.2, xyClearance=0.025, plateWidth=3, plateLength=2,
        plateType='Light', hasMagnetSockets=False, magnetSocketSize=0.65, magnetSocketDepth=0.24,
        hasScrewHoles=False, screwHoleSize=0.32, screwHeadSize=0.6,
        hasPadding=False, paddingLeft=0, paddingTop=0, paddingRight=0, paddingBottom=0,
        extraBottomThickness=0.64, verticalClearance=0.05, hasConnectionHoles=False, connectionHoleSize=0.32,
    )
    state.update(overrides)
    return types.SimpleNamespace(**state)

def allBodies(design):
    return [body for component in design.allComponents for body in component.bRepBodies if body.isVisible]

def shape(design):
    bodies = allBodies(design)
    if not bodies:
        return (0, 0, ())
    box = tuple(round(v * 10, 3) for v in (
        min(b.boundingBox.minPoint.x for b in bodies), min(b.boundingBox.minPoint.y for b in bodies), min(b.boundingBox.minPoint.z for b in bodies),
        max(b.boundingBox.maxPoint.x for b in bodies), max(b.boundingBox.maxPoint.y for b in bodies), max(b.boundingBox.maxPoint.z for b in bodies)))
    return (round(sum(b.volume for b in bodies), 4), sum(b.faces.count for b in bodies), box)

def unhealthy(design):
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

def generate(entry, app, state):
    """Run entry.generateBaseplate with `state` instead of the dialog; returns (design, ok, message)."""
    newDocument(app)
    design = adsk.fusion.Design.cast(app.activeProduct)
    original = entry.getInputsState
    entry.getInputsState = lambda: state
    args = types.SimpleNamespace(executeFailed=False, executeFailedMessage='')
    try:
        entry.generateBaseplate(args)
    finally:
        entry.getInputsState = original
    return design, not args.executeFailed, args.executeFailedMessage

CASES = [
    ('light 3x2 (dialog default)', {}),
    ('full 3x2', dict(plateType='Full')),
    ('light 3x2 magnets + screws', dict(hasMagnetSockets=True, hasScrewHoles=True)),
    ('skeletonized 3x2 magnets + screws', dict(plateType='Skeletonized', hasMagnetSockets=True, hasScrewHoles=True)),
    ('full 2x2 magnets + screws + connection holes + padding', dict(plateType='Full', plateWidth=2, hasMagnetSockets=True, hasScrewHoles=True,
        hasConnectionHoles=True, hasPadding=True, paddingLeft=0.5, paddingTop=0.3, paddingRight=0.2, paddingBottom=0.4)),
    ('skeletonized 3x2 magnets + screws + connection holes (fixed count)', dict(plateType='Skeletonized', hasMagnetSockets=True, hasScrewHoles=True, hasConnectionHoles=True)),
    ('skeletonized 1x1 magnets + screws', dict(plateType='Skeletonized', plateWidth=1, plateLength=1, hasMagnetSockets=True, hasScrewHoles=True)),
    ('full 4x3 magnets + screws', dict(plateType='Full', plateWidth=4, plateLength=3, hasMagnetSockets=True, hasScrewHoles=True)),
]

def upstreamGroup(fork, app):
    """Fork baseplates created from the dialog must match upstream exactly."""
    upstream = findUpstreamEntry()
    if upstream is None:
        print('[SKIP] upstream comparison: App Store build not loaded')
        return []
    results = []
    for label, overrides in CASES:
        forkDesign, forkOk, forkMessage = generate(fork, app, plateState(**overrides))
        forkShape, forkBad = shape(forkDesign), unhealthy(forkDesign)
        upstreamDesign, upstreamOk, upstreamMessage = generate(upstream, app, plateState(**overrides))
        upstreamShape = shape(upstreamDesign)
        passed = forkOk and upstreamOk and forkShape == upstreamShape and not forkBad
        detail = '' if forkOk and upstreamOk else f' failed: {forkMessage[:300]} {upstreamMessage[:300]}'
        print(f'[{"PASS" if passed else "FAIL"}] {label} same as upstream: fork={forkShape} upstream={upstreamShape} unhealthy={forkBad}{detail}')
        results.append(passed)
    return results

def plateEquivalence(fork, app, label, changes, finalOverrides, overrides):
    """Create with `overrides`, change gfp1_ parameters, compare with a plate created directly with
    `finalOverrides` (the edit must change the plate and match)."""
    design, ok, message = generate(fork, app, plateState(**overrides))
    if not ok:
        print(f'[FAIL] {label}: create failed {message[:300]}')
        return False
    before = shape(design)
    for suffix, expression in changes:
        design.userParameters.itemByName('gfp1_' + suffix).expression = expression
    adsk.doEvents()
    edited, bad = shape(design), unhealthy(design)
    merged = dict(overrides)
    merged.update(finalOverrides)
    directDesign, directOk, directMessage = generate(fork, app, plateState(**merged))
    direct = shape(directDesign)
    passed = directOk and edited != before and edited == direct and not bad
    print(f'[{"PASS" if passed else "FAIL"}] {label}: edited={edited} direct={direct} changed={edited != before} unhealthy={bad}{"" if directOk else " " + directMessage[:200]}')
    return passed

FULL_HOLES = dict(plateType='Full', hasMagnetSockets=True, hasScrewHoles=True)
SKELETON = dict(plateType='Skeletonized', hasMagnetSockets=True, hasScrewHoles=True)

def scalarsGroup(fork, app):
    """M5: base size, clearance, magnet/screw sizes, padding, extra bottom, vertical clearance."""
    checks = [
        ('base 42 -> 40 x 45 mm (full)', [('base_width', '40 mm'), ('base_length', '45 mm')], dict(baseWidth=4.0, baseLength=4.5), dict(plateType='Full')),
        ('xy clearance 0.25 -> 0.5 mm (full, magnets + screws)', [('xy_clearance', '0.5 mm')], dict(xyClearance=0.05), FULL_HOLES),
        ('magnet 6.5 -> 6 mm, depth 2.4 -> 2 mm (full)', [('magnet_diameter', '6 mm'), ('magnet_depth', '2 mm')], dict(magnetSocketSize=0.6, magnetSocketDepth=0.2), FULL_HOLES),
        ('screw 3.2 -> 3 mm, head 6 -> 7 mm (full)', [('screw_diameter', '3 mm'), ('screw_head_diameter', '7 mm')], dict(screwHoleSize=0.3, screwHeadSize=0.7), FULL_HOLES),
        ('extra bottom 6.4 -> 8 mm (full)', [('extra_bottom_thickness', '8 mm')], dict(extraBottomThickness=0.8), FULL_HOLES),
        ('vertical clearance 0.5 -> 1 mm (light)', [('vertical_clearance', '1 mm')], dict(verticalClearance=0.1), {}),
        ('padding left 5 -> 8 mm, top 3 -> 2 mm (full)', [('padding_left', '8 mm'), ('padding_top', '2 mm')], dict(paddingLeft=0.8, paddingTop=0.2),
         dict(plateType='Full', hasPadding=True, paddingLeft=0.5, paddingTop=0.3, paddingRight=0.2, paddingBottom=0.4)),
        ('magnet 6.5 -> 7 mm, base 42 -> 40 mm (skeletonized)', [('magnet_diameter', '7 mm'), ('base_width', '40 mm')], dict(magnetSocketSize=0.7, baseWidth=4.0), SKELETON),
        ('connection hole 3.2 -> 3 mm (skeletonized + connection holes)', [('connection_hole_diameter', '3 mm')], dict(connectionHoleSize=0.3),
         dict(SKELETON, hasConnectionHoles=True)),
    ]
    return [plateEquivalence(fork, app, *check) for check in checks]

def countGroup(fork, app):
    """M5: plate X/Y count (pockets as a feature pattern into a tool carrier)."""
    checks = [
        ('3x2 -> 4x3 (light)', [('plate_width_u', '4'), ('plate_length_u', '3')], dict(plateWidth=4, plateLength=3), {}),
        ('3x2 -> 2x1 (full, magnets + screws)', [('plate_width_u', '2'), ('plate_length_u', '1')], dict(plateWidth=2, plateLength=1), FULL_HOLES),
        ('3x2 -> 5x4 (skeletonized, magnets + screws)', [('plate_width_u', '5'), ('plate_length_u', '4')], dict(plateWidth=5, plateLength=4), SKELETON),
        ('1x1 -> 3x2 (skeletonized, magnets + screws)', [('plate_width_u', '3'), ('plate_length_u', '2')], dict(plateWidth=3, plateLength=2), dict(SKELETON, plateWidth=1, plateLength=1)),
        ('2x2 -> 3x2 (full, padding, magnets + screws)', [('plate_width_u', '3')], dict(plateWidth=3),
         dict(FULL_HOLES, plateWidth=2, plateLength=2, hasPadding=True, paddingLeft=0.5, paddingTop=0.3, paddingRight=0.2, paddingBottom=0.4)),
        ('3x2 -> 4x2 + base 40 mm (full)', [('plate_width_u', '4'), ('base_width', '40 mm')], dict(plateWidth=4, baseWidth=4.0), dict(plateType='Full')),
    ]
    results = [plateEquivalence(fork, app, *check) for check in checks]
    # with connection holes the plate keeps upstream's body patterns: the count is recorded only
    design, ok, _ = generate(fork, app, plateState(**dict(SKELETON, hasConnectionHoles=True)))
    comment = design.userParameters.itemByName('gfp1_plate_width_u').comment if ok else ''
    passed = ok and 'info only' in comment and 'info only' not in design.userParameters.itemByName('gfp1_base_width').comment
    print(f'[{"PASS" if passed else "FAIL"}] connection holes: plate count marked info only ({comment})')
    results.append(passed)
    return results

def stressGroup(fork, app, mixNames=None, sizes=None):
    """Sizes x plate types: creation identical to the App Store build, and after a count change
    identical to a plate created at the new size (Fusion pattern failures depend on size)."""
    upstream = findUpstreamEntry()
    mixes = [('light', {}), ('full, magnets + screws', FULL_HOLES), ('skeletonized, magnets + screws', SKELETON)]
    results = []
    for mixName, mix in [m for m in mixes if mixNames is None or m[0] in mixNames]:
        for width, length in sizes or [(1, 1), (2, 1), (3, 3), (4, 2), (5, 5), (6, 3)]:
            failures = []
            overrides = dict(mix, plateWidth=width, plateLength=length)
            design, ok, message = generate(fork, app, plateState(**overrides))
            if not ok:
                failures.append('create: ' + message[:200])
            else:
                created = shape(design)
                newWidth, newLength = width + 1, max(1, length - 1)
                design.userParameters.itemByName('gfp1_plate_width_u').expression = str(newWidth)
                design.userParameters.itemByName('gfp1_plate_length_u').expression = str(newLength)
                adsk.doEvents()
                edited, bad = shape(design), unhealthy(design)
                if upstream is not None:
                    upstreamDesign, upstreamOk, _ = generate(upstream, app, plateState(**overrides))
                    if upstreamOk and shape(upstreamDesign) != created:
                        failures.append(f'create differs from upstream: {created} vs {shape(upstreamDesign)}')
                fresh, freshOk, _ = generate(fork, app, plateState(**dict(mix, plateWidth=newWidth, plateLength=newLength)))
                if bad or not freshOk or shape(fresh) != edited:
                    failures.append(f'after {newWidth}x{newLength}: {bad[:2]} edited={edited} fresh={shape(fresh) if freshOk else "failed"}')
            closeCreatedDocuments()
            print(f'[{"FAIL" if failures else "PASS"}] {mixName} {width}x{length}' + ('' if not failures else ': ' + '; '.join(failures)))
            results.append(not failures)
    return results

GROUPS = {
    'upstream': upstreamGroup,
    'scalars': scalarsGroup,
    'count': countGroup,
    'stress': stressGroup,
}

def runSuite(groups=None):
    app = adsk.core.Application.get()
    fork = loadForkEntry()
    results = []
    try:
        for name, group in GROUPS.items():
            if groups is None or name in groups:
                print(f'== {name}')
                results.extend(group(fork, app))
    finally:
        closeCreatedDocuments()
    print(f'SUMMARY: {sum(results)}/{len(results)} passed')
    return results

def run(_context: str):
    runSuite()
