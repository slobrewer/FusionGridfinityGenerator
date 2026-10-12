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

GROUPS = {
    'upstream': upstreamGroup,
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
