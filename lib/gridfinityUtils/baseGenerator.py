import adsk.core, adsk.fusion, traceback, math
import os

from .sketchUtils import createRectangle
from ...lib.gridfinityUtils.baseGeneratorInput import BaseGeneratorInput
from . import sketchUtils, const, edgeUtils, commonUtils, combineUtils, faceUtils, extrudeUtils, shapeUtils, geometryUtils
from ...lib import fusion360utils as futil
from ... import config
from .dim import toValueInput, asPoint3D, applyExpression, isParametric, DimPoint

app = adsk.core.Application.get()
ui = app.userInterface

def createCircleAtPointSketch(
    plane: adsk.core.Base,
    radius: float,
    circleCenterPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    circleSketch: adsk.fusion.Sketch = sketches.add(plane)
    circleCenterOnSketch = sketchUtils.modelToSketch(circleSketch, circleCenterPoint)
    dimensions: adsk.fusion.SketchDimensions = circleSketch.sketchDimensions
    sketchUtils.convertToConstruction(circleSketch.sketchCurves)
    circle = circleSketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(float(circleCenterOnSketch.x), float(circleCenterOnSketch.y), 0),
        float(radius),
    )
    diameterDimension = dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y * 2, 0),
        True,
    )
    applyExpression(diameterDimension, radius * 2)
    centerXDimension = dimensions.addDistanceDimension(
        circleSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
        True
        )
    centerYDimension = dimensions.addDistanceDimension(
        circleSketch.originPoint,
        circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
        True
        )
    applyExpression(centerXDimension, circleCenterOnSketch.x)
    applyExpression(centerYDimension, circleCenterOnSketch.y)

    return (circleSketch, circle)

def createTabAtCircleEdgeSketch(
    plane: adsk.core.Base,
    radius: float,
    circleCenterPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    circleSketch, circle = createCircleAtPointSketch(
        plane,
        radius,
        circleCenterPoint,
        targetComponent,
    )
    centerX, centerY, centerZ, radiusValue = float(circleCenterPoint.x), float(circleCenterPoint.y), float(circleCenterPoint.z), float(radius)
    circleCenterOnSketch = geometryUtils.pointToXY(circleSketch.modelToSketchSpace(adsk.core.Point3D.create(centerX, centerY, centerZ)))
    angularPointOnSketch = geometryUtils.pointToXY(circleSketch.modelToSketchSpace(
        adsk.core.Point3D.create(centerX + radiusValue, centerY + radiusValue, centerZ)
    ))
    dimensions: adsk.fusion.SketchDimensions = circleSketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = circleSketch.geometricConstraints
    sketchUtils.convertToConstruction(circleSketch.sketchCurves)
    verticalConstructionLine = circleSketch.sketchCurves.sketchLines.addByTwoPoints(
        circleCenterOnSketch,
        adsk.core.Point3D.create(circleCenterOnSketch.x, circleCenterOnSketch.y + radiusValue, circleCenterOnSketch.z)
    )
    verticalConstructionLine.isConstruction = True
    diagonalConstructionLine = circleSketch.sketchCurves.sketchLines.addByTwoPoints(
        circleCenterOnSketch,
        angularPointOnSketch,
    )
    diagonalConstructionLine.isConstruction = True
    constraints.addVertical(verticalConstructionLine)
    dimensions.addAngularDimension(
        diagonalConstructionLine,
        verticalConstructionLine,
        angularPointOnSketch,
    )
    constraints.addCoincident(
        verticalConstructionLine.startSketchPoint,
        circle.centerSketchPoint,
    )
    constraints.addCoincident(
        verticalConstructionLine.endSketchPoint,
        circle,
    )
    constraints.addCoincident(
        diagonalConstructionLine.startSketchPoint,
        circle.centerSketchPoint,
    )
    constraints.addCoincident(
        diagonalConstructionLine.endSketchPoint,
        circle,
    )
    circle = circleSketch.sketchCurves.sketchCircles.addByCenterRadius(
        diagonalConstructionLine.endSketchPoint,
        radiusValue / 2,
    )
    tabRadiusDimension = dimensions.addRadialDimension(
        circle,
        circleCenterOnSketch,
    )
    applyExpression(tabRadiusDimension, radius / 2)

    return circleSketch

INVERSE_SQRT2 = 1 / math.sqrt(2)

def rotatedByMinus45(center: DimPoint, u, v) -> DimPoint:
    """center + (u, v) rotated by -45 degrees about +Z (u, v may be Dims)."""
    return DimPoint(center.x + (u + v) * INVERSE_SQRT2, center.y + (v - u) * INVERSE_SQRT2, 0)

def createGrooveLayer(
    plane: adsk.core.Base,
    planeOffset,
    height,
    outline: list,
    clipRadius,
    center: DimPoint,
    targetComponent: adsk.fusion.Component,
    cutFrom: adsk.fusion.BRepBody = None,
):
    """Prism from the polygon `outline` (model points), optionally clipped by a circle of
    `clipRadius` around `center`, sketched on `plane` offset by `planeOffset`. A new body, or with
    `cutFrom` a cut from that body (returns the feature)."""
    planeInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(plane, toValueInput(planeOffset))
    layerPlane = targetComponent.constructionPlanes.add(planeInput)
    layerPlane.isLightBulbOn = False
    sketch: adsk.fusion.Sketch = targetComponent.sketches.add(layerPlane)
    sketch.name = 'Magnet groove layer sketch'
    sketchUtils.createPolygon([sketchUtils.modelToSketch(sketch, point) for point in outline], sketch)
    if clipRadius is not None:
        centerOnSketch = sketchUtils.modelToSketch(sketch, center)
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(float(centerOnSketch.x), float(centerOnSketch.y), 0),
            float(clipRadius),
        )
        dimensions = sketch.sketchDimensions
        applyExpression(dimensions.addDiameterDimension(circle, adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x + 1, circle.centerSketchPoint.geometry.y + 1, 0), True), clipRadius * 2)
        applyExpression(dimensions.addDistanceDimension(sketch.originPoint, circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation, adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0), True), centerOnSketch.x)
        applyExpression(dimensions.addDistanceDimension(sketch.originPoint, circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation, adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0), True), centerOnSketch.y)
    def arcCount(profile):
        return sum(1 for curve in profile.profileLoops.item(0).profileCurves if curve.geometry.objectType == adsk.core.Arc3D.classType())
    # clipped: the region bounded by both strip edges and both arcs; unclipped: the only profile
    profile = max(sketch.profiles, key=arcCount) if clipRadius is not None else sketch.profiles.item(0)
    extrudeFeatures = targetComponent.features.extrudeFeatures
    if cutFrom is not None:
        extrudeInput = extrudeFeatures.createInput(profile, adsk.fusion.FeatureOperations.CutFeatureOperation)
        extrudeInput.setDistanceExtent(False, toValueInput(height))
        extrudeInput.participantBodies = [cutFrom]
        extrude = extrudeFeatures.add(extrudeInput)
        extrude.name = 'Magnet groove layer'
        return extrude
    extrude = extrudeFeatures.addSimple(profile, toValueInput(height), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = 'Magnet groove layer'
    return extrude.bodies.item(0)

def taperedSectionExtrude(
    plane: adsk.core.Base,
    width,
    length,
    startPoint: DimPoint,
    cornerRadius,
    depth: float,
    taper: bool,
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
    name: str,
) -> adsk.fusion.ExtrudeFeature:
    """Rounded rectangle on `plane` extruded `depth` downwards into `targetBody`; with `taper` the
    sides lean inwards at 45 degrees (what a 45 degree equal-distance chamfer of that depth gives)."""
    sketch: adsk.fusion.Sketch = targetComponent.sketches.add(plane)
    sketch.name = name + ' sketch'
    sketchUtils.createRoundedRectangle(width, length, sketchUtils.modelToSketch(sketch, startPoint), cornerRadius, sketch)
    extrudeInput = targetComponent.features.extrudeFeatures.createInput(sketch.profiles.item(0), adsk.fusion.FeatureOperations.JoinFeatureOperation)
    extrudeInput.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(depth)),
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        adsk.core.ValueInput.createByString('-45 deg' if taper else '0 deg'),
    )
    extrudeInput.participantBodies = [targetBody]
    extrude = targetComponent.features.extrudeFeatures.add(extrudeInput)
    extrude.name = name
    return extrude

def offsetXYPlane(z, name: str, targetComponent: adsk.fusion.Component):
    planeInput = targetComponent.constructionPlanes.createInput()
    planeInput.setByOffset(targetComponent.xYConstructionPlane, toValueInput(z))
    plane = targetComponent.constructionPlanes.add(planeInput)
    plane.name = name
    plane.isLightBulbOn = False
    return plane

def createTaperedBaseInto(
    input: BaseGeneratorInput,
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.ExtrudeFeature:
    """The gridfinity base profile built inside `targetBody`: top section tapered 45 degrees,
    straight mid section, bottom section tapered 45 degrees. Returns the lowest extrude."""
    origin = input.originPoint
    top = const.BIN_BASE_TOP_SECTION_HEIGH
    mid = const.BIN_BASE_MID_SECTION_HEIGH
    bottom = const.BIN_BASE_BOTTOM_SECTION_HEIGH
    taperedSectionExtrude(
        offsetXYPlane(origin.z, 'Base top section plane', targetComponent),
        input.baseWidth, input.baseLength, DimPoint(origin.x, origin.y, 0), input.cornerFilletRadius,
        top, True, targetBody, targetComponent, 'Base top section extrude')
    # the top section ends inset by its own height on every side
    lowerPlane = offsetXYPlane(origin.z - top, 'Base mid section plane', targetComponent)
    lowerArguments = (input.baseWidth - top * 2, input.baseLength - top * 2, DimPoint(origin.x + top, origin.y + top, 0), input.cornerFilletRadius - top)
    if not input.hasBottomChamfer:
        return taperedSectionExtrude(lowerPlane, *lowerArguments, mid + bottom, False, targetBody, targetComponent, 'Base mid section extrude')
    taperedSectionExtrude(lowerPlane, *lowerArguments, mid, False, targetBody, targetComponent, 'Base mid section extrude')
    return taperedSectionExtrude(
        offsetXYPlane(origin.z - top - mid, 'Base bottom section plane', targetComponent),
        *lowerArguments, bottom, True, targetBody, targetComponent, 'Base bottom section extrude')

def createSingleGridfinityBaseBody(
    input: BaseGeneratorInput,
    targetComponent: adsk.fusion.Component,
    combineInto: adsk.fusion.BRepBody = None,
    combine=None,
):
    """One gridfinity base. With `combineInto`, the base is combined into that body (`combine`,
    e.g. combineUtils.joinBodies) before its screw/magnet holes are cut from that body, so that every
    feature can be repeated by a feature pattern (see createBaseFeaturePattern)."""
    actual_base_width = input.baseWidth
    actual_base_length = input.baseLength
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    # When joining into another body, build the base straight into that body from sketches, with
    # tapered extrudes in place of the corner fillet and 45 degree chamfers (same shape). A feature
    # pattern of these features then creates no bodies and has no fillet/chamfer: new bodies inside
    # a feature pattern lose track of their targets in some copies (MULTIPLE_TARGET_ERROR, "All
    # tool bodies are lost"), and fillets/chamfers fail where neighbouring bases meet.
    joinEarly = combineInto is not None and combine is combineUtils.joinBodies
    if joinEarly:
        baseBody = combineInto
        baseBottomExtrude = createTaperedBaseInto(input, combineInto, targetComponent)
    else:
        baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        baseConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, toValueInput(input.originPoint.z))
        baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
        baseConstructionPlane.name = 'Base plate construction plane'
        # create rectangle for the base
        sketches: adsk.fusion.Sketches = targetComponent.sketches
        basePlateSketch: adsk.fusion.Sketch = sketches.add(baseConstructionPlane)
        basePlateSketch.name = 'Base plate sketch'
        createRectangle(actual_base_width, actual_base_length, sketchUtils.modelToSketch(basePlateSketch, input.originPoint), basePlateSketch)

        # extrude top section
        topSectionExtrudeDepth = adsk.core.ValueInput.createByReal(const.BIN_BASE_TOP_SECTION_HEIGH)
        topSectionExtrudeInput = extrudeFeatures.createInput(basePlateSketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        topSectionExtrudeExtent = adsk.fusion.DistanceExtentDefinition.create(topSectionExtrudeDepth)
        topSectionExtrudeInput.setOneSideExtent(topSectionExtrudeExtent,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
            adsk.core.ValueInput.createByReal(0))
        topSectionExtrudeFeature = extrudeFeatures.add(topSectionExtrudeInput)
        topSectionExtrudeFeature.name = 'Base top section extrude'
        baseBody = topSectionExtrudeFeature.bodies.item(0)
        baseBody.name = 'Base'

        # fillet on corners
        filletFeatures: adsk.fusion.FilletFeatures = features.filletFeatures
        filletInput = filletFeatures.createInput()
        filletInput.isRollingBallCorner = True
        fillet_edges = edgeUtils.selectEdgesByLength(baseBody.faces, const.BIN_BASE_TOP_SECTION_HEIGH, const.DEFAULT_FILTER_TOLERANCE)
        filletInput.edgeSetInputs.addConstantRadiusEdgeSet(fillet_edges, toValueInput(input.cornerFilletRadius), True)
        filletFeatures.add(filletInput).name = 'Base corner fillet'

        # chamfer top section
        chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
        chamferInput = chamferFeatures.createInput2()
        chamfer_edges = adsk.core.ObjectCollection.create()
        # use one edge for chamfer, the rest will be automatically detected with tangent chain condition
        chamfer_edges.add(topSectionExtrudeFeature.endFaces.item(0).edges.item(0))
        chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
            topSectionExtrudeDepth,
            True)
        chamferFeatures.add(chamferInput)

        # extrude mid/bottom section
        baseBottomExtrude = extrudeUtils.simpleDistanceExtrude(
            topSectionExtrudeFeature.endFaces.item(0),
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            const.BIN_BASE_MID_SECTION_HEIGH + const.BIN_BASE_BOTTOM_SECTION_HEIGH,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [baseBody],
            targetComponent
        )

        if input.hasBottomChamfer:
            # chamfer bottom section
            chamferFeatures: adsk.fusion.ChamferFeatures = features.chamferFeatures
            chamferInput = chamferFeatures.createInput2()
            chamfer_edges = commonUtils.objectCollectionFromList(faceUtils.getBottomFace(baseBottomExtrude.bodies.item(0)).edges)
            chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamfer_edges,
                adsk.core.ValueInput.createByReal(const.BIN_BASE_BOTTOM_SECTION_HEIGH),
                True)
            chamferFeatures.add(chamferInput)

    hasHoles = input.hasScrewHoles or input.hasMagnetCutouts
    baseBottomPlane = baseBottomExtrude.endFaces.item(0)
    baseBottomZ = baseBottomPlane.boundingBox.minPoint.z
    if combineInto is not None:
        if hasHoles:
            # the bottom face goes away when the base is combined; a plane made from it keeps its
            # position and sketch orientation for the hole cutouts
            bottomPlaneInput = targetComponent.constructionPlanes.createInput()
            bottomPlaneInput.setByOffset(baseBottomPlane, adsk.core.ValueInput.createByReal(0))
            baseBottomPlane = targetComponent.constructionPlanes.add(bottomPlaneInput)
            baseBottomPlane.name = 'Base bottom plane'
            baseBottomPlane.isLightBulbOn = False
        if not joinEarly:
            combine(combineInto, commonUtils.objectCollectionFromList([baseBody]), targetComponent)
    holeFeaturesStart = targetComponent.parentDesign.timeline.count
    cutFrom = combineInto

    # screw holes
    circularPatternFeatures = features.circularPatternFeatures
    cutoutBodies = adsk.core.ObjectCollection.create()

    baseHoleCenterPoint = DimPoint(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        baseBottomZ
    )
    cutoutCenterPoint = DimPoint(baseHoleCenterPoint.x, baseHoleCenterPoint.y, 0)
    if input.hasScrewHoles:
        screwHoleBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -const.BIN_BASE_HEIGHT,
            input.screwHolesDiameter / 2,
            cutoutCenterPoint,
            targetComponent,
            cutFrom=cutFrom,
        )
        if cutFrom is None:
            cutoutBodies.add(screwHoleBody)

    # magnet cutouts
    if input.hasMagnetCutouts:
        magnetSocketBody = shapeUtils.simpleCylinder(
            baseBottomPlane,
            0,
            -input.magnetCutoutsDepth,
            input.magnetCutoutsDiameter / 2,
            cutoutCenterPoint,
            targetComponent,
            cutFrom=cutFrom,
        )
        if cutFrom is None:
            cutoutBodies.add(magnetSocketBody)

        # magnet tab cutouts
        if input.hasMagnetCutoutsTabs:
            magnetTabCutoutSketch = createTabAtCircleEdgeSketch(
                baseBottomPlane,
                input.magnetCutoutsDiameter / 2,
                cutoutCenterPoint,
                targetComponent,
            )
            magnetTabCutoutSketch.name = "Cutout tab sketch"

            magnetTabCutoutExtrude = extrudeUtils.simpleDistanceExtrude(
                magnetTabCutoutSketch.profiles.item(0),
                adsk.fusion.FeatureOperations.CutFeatureOperation if cutFrom is not None else adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                input.magnetCutoutsDepth,
                adsk.fusion.ExtentDirections.NegativeExtentDirection,
                [cutFrom] if cutFrom is not None else [],
                targetComponent,
            )
            if cutFrom is None:
                cutoutBodies.add(magnetTabCutoutExtrude.bodies.item(0))
        
        if input.hasScrewHoles and (const.BIN_BASE_HEIGHT - input.magnetCutoutsDepth) > const.BIN_MAGNET_HOLE_GROOVE_DEPTH:
            # Print-helper groove above the magnet socket: a strip as wide as the screw hole across
            # the socket (clipped by it), then a screw-hole-sized square, both turned -45 degrees.
            # Upstream intersects a cylinder with two boxes and rotates the result with a move;
            # drawing the layers already rotated avoids both, which break inside a feature pattern
            # (IDENTICAL_TARGET_AND_TOOL_BODY, a rotate axis that stays with the first base).
            stripHalfLength = input.magnetCutoutsDiameter / 2 + 0.1
            halfScrew = input.screwHolesDiameter / 2
            strip = [rotatedByMinus45(cutoutCenterPoint, u, v) for u, v in (
                (-stripHalfLength, -halfScrew), (stripHalfLength, -halfScrew), (stripHalfLength, halfScrew), (-stripHalfLength, halfScrew))]
            grooveLayer1 = createGrooveLayer(
                baseBottomPlane,
                -input.magnetCutoutsDepth,
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                strip,
                input.magnetCutoutsDiameter / 2,
                cutoutCenterPoint,
                targetComponent,
                cutFrom=cutFrom,
            )
            # the screw-sized square turned by 45 degrees has its corners on the axes through the centre
            halfDiagonal = input.screwHolesDiameter * INVERSE_SQRT2
            square = [
                DimPoint(cutoutCenterPoint.x + halfDiagonal, cutoutCenterPoint.y, 0),
                DimPoint(cutoutCenterPoint.x, cutoutCenterPoint.y + halfDiagonal, 0),
                DimPoint(cutoutCenterPoint.x - halfDiagonal, cutoutCenterPoint.y, 0),
                DimPoint(cutoutCenterPoint.x, cutoutCenterPoint.y - halfDiagonal, 0),
            ]
            grooveLayer2 = createGrooveLayer(
                baseBottomPlane,
                -(input.magnetCutoutsDepth + const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2),
                -const.BIN_MAGNET_HOLE_GROOVE_DEPTH / 2,
                square,
                None,
                cutoutCenterPoint,
                targetComponent,
                cutFrom=cutFrom,
            )
            if cutFrom is None:
                grooveLayer1.name = "Groove layer 1 body"
                grooveLayer2.name = "Groove layer 2 body"
                cutoutBodies.add(grooveLayer1)
                cutoutBodies.add(grooveLayer2)


    if hasHoles:
        if combineInto is not None:
            # this corner's holes were cut straight from the combined body; repeat them with a
            # pattern of *features* (a pattern of bodies cannot be repeated by the outer pattern,
            # and cutout bodies combined inside nested patterns go missing in some copies)
            holeFeatures = timelineFeaturesSince(targetComponent.parentDesign, holeFeaturesStart)
        elif cutoutBodies.count > 1:
            joinFeature = combineUtils.joinBodies(cutoutBodies.item(0), commonUtils.objectCollectionFromList(list(cutoutBodies)[1:]), targetComponent)
            cutoutBodies = commonUtils.objectCollectionFromList(joinFeature.bodies)

        baseXZMidPlaneInput = targetComponent.constructionPlanes.createInput()
        baseXZMidPlaneInput.setByOffset(targetComponent.xZConstructionPlane, toValueInput(input.baseLength / 2 - input.xyClearance))
        baseXZMidPlane = targetComponent.constructionPlanes.add(baseXZMidPlaneInput)
        baseXZMidPlane.name = "Base XZ mid plane"
        baseXZMidPlane.isLightBulbOn = False
        baseYZMidPlaneInput = targetComponent.constructionPlanes.createInput()
        baseYZMidPlaneInput.setByOffset(targetComponent.yZConstructionPlane, toValueInput(input.baseWidth / 2 - input.xyClearance))
        baseYZMidPlane = targetComponent.constructionPlanes.add(baseYZMidPlaneInput)
        baseYZMidPlane.name = "Base YZ mid plane"
        baseYZMidPlane.isLightBulbOn = False
        patternAxisInput = targetComponent.constructionAxes.createInput()
        patternAxisInput.setByTwoPlanes(
            baseXZMidPlane,
            baseYZMidPlane
        )
        baseCenterAxis = targetComponent.constructionAxes.add(patternAxisInput)
        baseCenterAxis.name = "Base center axis"
        baseCenterAxis.isLightBulbOn = False
        if combineInto is not None:
            patternInput = circularPatternFeatures.createInput(
                commonUtils.objectCollectionFromList(holeFeatures),
                baseCenterAxis,
            )
            patternInput.quantity = adsk.core.ValueInput.createByString("4")
            patternInput.patternComputeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
            circularPatternFeatures.add(patternInput).name = 'Base holes pattern'
        else:
            patternInput = circularPatternFeatures.createInput(
                cutoutBodies,
                baseCenterAxis,
            )
            patternInput.quantity = adsk.core.ValueInput.createByString("4")
            patternFeature = circularPatternFeatures.add(patternInput)
            combineUtils.cutBody(baseBody, commonUtils.objectCollectionFromList(list(cutoutBodies) + list(patternFeature.bodies)), targetComponent)

    return baseBody


def createSingleBaseBodyWithClearance(input: BaseGeneratorInput, targetComponent: adsk.fusion.Component):
    """
    deprecated:: produced inconsistent results where fillets on the corners would not align properly with outer radius
    """
    features = targetComponent.features
    # create base
    baseBody = createSingleGridfinityBaseBody(input, targetComponent)

    # offset side faces
    offsetFacesInput = features.offsetFeatures.createInput(
        commonUtils.objectCollectionFromList([face for face in list(baseBody.faces) if not faceUtils.isZNormal(face)]),
        adsk.core.ValueInput.createByReal(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        False
    )
    offsetFacesFeature = features.offsetFeatures.add(offsetFacesInput)
    offsetFacesFeature.name = "bin base side faces"

    # original solid body might be included into feature bodies array, find created surfaces using isSolid flag
    offsetSurfaceBodies = [body for body in list(offsetFacesFeature.bodies) if not body.isSolid][0]
    offsetSurfaceBodies.name = "bin base side faces"

    extentEdge = faceUtils.getTopHorizontalEdge(offsetSurfaceBodies.edges)
    extendClearanceSurfaceFeatureInput = features.extendFeatures.createInput(
        commonUtils.objectCollectionFromList([extentEdge]),
        adsk.core.ValueInput.createByReal(input.xyClearance * 2),
        adsk.fusion.SurfaceExtendTypes.NaturalSurfaceExtendType,
        True
    )
    extendFeature = features.extendFeatures.add(extendClearanceSurfaceFeatureInput)

    # thicken faces to add clearance
    thickenFaces = commonUtils.objectCollectionFromList(offsetFacesFeature.faces, extendFeature.faces);
    thickenFeatureInput = features.thickenFeatures.createInput(
        thickenFaces,
        adsk.core.ValueInput.createByReal(input.xyClearance),
        False,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        False,
    )
    thickenFeaure = features.thickenFeatures.add(thickenFeatureInput)
    thickenFeaure.name = "clearance"
    thickenFeaure.bodies.item(0).name = "bin base clearance layer"
    features.removeFeatures.add(offsetSurfaceBodies)

    # thickened body would go beyond the bottom face, use bounding box to make bottom flat
    clearanceBoundingBox = extrudeUtils.createBoxAtPoint(
        input.baseWidth,
        input.baseLength,
        -const.BIN_BASE_HEIGHT,
        targetComponent,
        adsk.core.Point3D.create(input.originPoint.x - input.xyClearance, input.originPoint.y - input.xyClearance, input.originPoint.z),
        )
    clearanceBoundingBox.name = "clearance bounding box"
    clearanceBoundingBox.bodies.item(0).name = "clearance bounding box"
    combineFeatureInput = features.combineFeatures.createInput(
        thickenFeaure.bodies.item(0),
        commonUtils.objectCollectionFromList(clearanceBoundingBox.bodies)
    )
    combineFeatureInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    features.combineFeatures.add(combineFeatureInput)
    combineUtils.joinBodies(baseBody, commonUtils.objectCollectionFromList(thickenFeaure.bodies), targetComponent)
    return baseBody

def createBaseBodyPattern(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetComponent: adsk.fusion.Component,
):
    baseBody = createSingleGridfinityBaseBody(baseConfiguration, targetComponent)
    features = targetComponent.features
    # replicate base in a rectangular pattern
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()
    patternInputBodies.add(baseBody)
    patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
        targetComponent.xConstructionAxis,
        adsk.core.ValueInput.createByReal(basesXCount),
        toValueInput(baseConfiguration.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = adsk.core.ValueInput.createByReal(basesYCount)
    patternInput.distanceTwo = toValueInput(baseConfiguration.baseLength)
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    return list(rectangularPattern.bodies) + [baseBody]

def timelineFeaturesSince(design: adsk.fusion.Design, firstIndex: int) -> list:
    """Features (not sketches / construction geometry) added to the timeline from firstIndex on."""
    features = []
    for index in range(firstIndex, design.timeline.count):
        entity = design.timeline.item(index).entity
        if entity is not None and adsk.fusion.Feature.cast(entity) is not None:
            features.append(entity)
    return features

def createBaseFeaturePattern(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetBody: adsk.fusion.BRepBody,
    targetComponent: adsk.fusion.Component,
    combine=combineUtils.joinBodies,
    computeOption=adsk.fusion.PatternComputeOptions.AdjustPatternCompute,
    spacing=None,
):
    """One base combined into `targetBody` (joined, or cut with combine=combineUtils.cutBody),
    repeated by a pattern of its *features*.

    A pattern of base bodies followed by a Combine cannot follow a count change (new instances stay
    loose bodies, removed ones leave lost references); a feature pattern that includes the Combine
    regenerates as one body for any count, so the counts may be Dims.
    `spacing` (x, y) defaults to the base size; lip notch cutouts are wider than their spacing.
    """
    spacingX, spacingY = spacing if spacing is not None else (baseConfiguration.baseWidth, baseConfiguration.baseLength)
    design = targetComponent.parentDesign
    firstIndex = design.timeline.count
    createSingleGridfinityBaseBody(baseConfiguration, targetComponent, combineInto=targetBody, combine=combine)
    baseFeatures = timelineFeaturesSince(design, firstIndex)
    if float(basesXCount) * float(basesYCount) <= 1 and not isParametric(basesXCount, basesYCount):
        return None
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = targetComponent.features.rectangularPatternFeatures
    patternInput = rectangularPatternFeatures.createInput(commonUtils.objectCollectionFromList(baseFeatures),
        targetComponent.xConstructionAxis,
        toValueInput(basesXCount),
        toValueInput(spacingX),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = toValueInput(basesYCount)
    patternInput.distanceTwo = toValueInput(spacingY)
    patternInput.patternComputeOption = computeOption
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    rectangularPattern.name = 'Base pattern'
    return rectangularPattern

BASE_CARRIER_THICKNESS = 0.005
BASE_CARRIER_INSET = 0.4

def createBaseCarrier(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetComponent: adsk.fusion.Component,
) -> adsk.fusion.BRepBody:
    """A 0.05 mm plate on top of the bases, inside the bin floor and away from its rounded corners.

    The base pattern joins every base into this plate before the bin body exists: in a feature
    pattern whose combines target a complex body (the finished bin), some copies fail to find
    their target (MULTIPLE_TARGET_ERROR) depending on size and feature mix. The plate is later
    joined into the bin body as one body, whatever the count, and adds no material of its own."""
    xyClearance = baseConfiguration.xyClearance
    carrier = extrudeUtils.createBoxAtPoint(
        baseConfiguration.baseWidth * basesXCount - xyClearance * 2 - BASE_CARRIER_INSET * 2,
        baseConfiguration.baseLength * basesYCount - xyClearance * 2 - BASE_CARRIER_INSET * 2,
        BASE_CARRIER_THICKNESS,
        targetComponent,
        DimPoint(baseConfiguration.originPoint.x + xyClearance + BASE_CARRIER_INSET, baseConfiguration.originPoint.y + xyClearance + BASE_CARRIER_INSET, baseConfiguration.originPoint.z),
    )
    carrier.name = 'Base carrier'
    body = carrier.bodies.item(0)
    body.name = 'Bases'
    return body

def cutBaseClearance(
    baseConfiguration: BaseGeneratorInput,
    basesXCount,
    basesYCount,
    targetComponent: adsk.fusion.Component,
):
    actual_base_width = baseConfiguration.baseWidth * basesXCount - baseConfiguration.xyClearance * 2
    actual_base_length = baseConfiguration.baseLength * basesYCount - baseConfiguration.xyClearance * 2
    features = targetComponent.features
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(targetComponent.xYConstructionPlane, toValueInput(baseConfiguration.originPoint.z))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    baseClearanceCutSketch: adsk.fusion.Sketch = sketches.add(baseConstructionPlane)
    baseClearanceCutSketch.name = "Base clearance cut sketch"
    innerRectangle = createRectangle(
        actual_base_width,
        actual_base_length,
        sketchUtils.modelToSketch(baseClearanceCutSketch, DimPoint(
            baseConfiguration.originPoint.x + baseConfiguration.xyClearance,
            baseConfiguration.originPoint.y + baseConfiguration.xyClearance,
            baseConfiguration.originPoint.z,
        )),
        baseClearanceCutSketch
    )
    sketchArcs = baseClearanceCutSketch.sketchCurves.sketchArcs
    geometricConstraints = baseClearanceCutSketch.geometricConstraints
    sketchDimensions = baseClearanceCutSketch.sketchDimensions

    [side1, side2, side3, side4] = list(innerRectangle)
    filletRadius = baseConfiguration.cornerFilletRadius - baseConfiguration.xyClearance
    fillet1 = sketchArcs.addFillet(side1, side1.endSketchPoint.geometry, side2, side2.startSketchPoint.geometry, float(filletRadius))
    fillet2 = sketchArcs.addFillet(side2, side2.endSketchPoint.geometry, side3, side3.startSketchPoint.geometry, float(filletRadius))
    fillet3 = sketchArcs.addFillet(side3, side3.endSketchPoint.geometry, side4, side4.startSketchPoint.geometry, float(filletRadius))
    fillet4 = sketchArcs.addFillet(side4, side4.endSketchPoint.geometry, side1, side1.startSketchPoint.geometry, float(filletRadius))

    geometricConstraints.addEqual(fillet1, fillet2)
    geometricConstraints.addEqual(fillet2, fillet3)
    geometricConstraints.addEqual(fillet3, fillet4)
    filletRadiusDimension = sketchDimensions.addRadialDimension(fillet1, fillet1.startSketchPoint.geometry)
    applyExpression(filletRadiusDimension, filletRadius)

    baseClearanceCutSketch.offset(commonUtils.objectCollectionFromList([fillet1, fillet2, fillet3, fillet4, side1, side2, side3, side4]), asPoint3D(baseConfiguration.originPoint), 1)

    cuttingProfile = min(list(baseClearanceCutSketch.profiles), key=lambda x: x.boundingBox.minPoint.x)
    clearanceCutExtrudeInput = features.extrudeFeatures.createInput(
        cuttingProfile,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    clearanceCutExtrudeInput.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(100)),
    )
    # no explicit participants: the cut then applies to whatever bodies it meets on every recompute.
    # An explicit list (upstream used all current bodies) loses its reference when the bin count
    # changes ("Body 1 missing").
    clearanceCutExtrude = features.extrudeFeatures.add(clearanceCutExtrudeInput)
    clearanceCutExtrude.name = "Base side clearance cut"