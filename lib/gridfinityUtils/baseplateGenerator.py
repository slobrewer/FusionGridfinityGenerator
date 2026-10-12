import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, commonUtils, filletUtils, combineUtils, faceUtils, extrudeUtils, sketchUtils, baseGenerator, patternUtils, shapeUtils, geometryUtils
from .baseGeneratorInput import BaseGeneratorInput
from .baseplateGeneratorInput import BaseplateGeneratorInput
from .dim import Dim, DimPoint, dmax, toValueInput, applyExpression, isParametric

def createPocketToolBodies(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component):
    """Upstream's pocket tools: one base pocket body with its extra cutouts, repeated by a body
    pattern. Used when the plate count is fixed (with connection holes)."""
    features = targetComponent.features
    cutoutInput = BaseGeneratorInput()
    cutoutInput.xyClearance = input.xyClearance
    cutoutInput.originPoint = geometryUtils.createOffsetPoint(
        targetComponent.originConstructionPoint.geometry,
        byX=-cutoutInput.xyClearance * 2,
        byY=-cutoutInput.xyClearance * 2,
    )
    cutoutInput.baseWidth = input.baseWidth + cutoutInput.xyClearance * 2
    cutoutInput.baseLength = input.baseLength + cutoutInput.xyClearance * 2
    cutoutInput.cornerFilletRadius = input.cornerFilletRadius + cutoutInput.xyClearance
    baseBody = baseGenerator.createSingleGridfinityBaseBody(cutoutInput, targetComponent)

    cuttingTools: list[adsk.fusion.BRepBody] = [baseBody]
    extraCutoutBodies: list[adsk.fusion.BRepBody] = []

    holeCenterPoint = DimPoint(
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        const.DIMENSION_SCREW_HOLES_OFFSET - input.xyClearance,
        0
    )

    connectionHoleYTool = None
    connectionHoleXTool = None

    if input.hasSkeletonizedBottom:
        centerCutoutExtrudeFeature, cutoutCornerPoint = createSkeletonCutout(input, faceUtils.getBottomFace(baseBody), holeCenterPoint, targetComponent)

        constructionAxisInput: adsk.fusion.ConstructionAxisInput = targetComponent.constructionAxes.createInput()
        constructionAxisInput.setByNormalToFaceAtPoint(
            faceUtils.getBottomFace(baseBody),
            cutoutCornerPoint,
        )
        constructionAxis = targetComponent.constructionAxes.add(constructionAxisInput)
        constructionAxis.isLightBulbOn = False

        centerCutoutPattern = patternUtils.circPattern(
            commonUtils.objectCollectionFromList(centerCutoutExtrudeFeature.bodies),
            constructionAxis,
            4,
            targetComponent,
        )
        centerCutoutBody = centerCutoutExtrudeFeature.bodies.item(0)
        combineUtils.joinBodies(
            centerCutoutBody,
            commonUtils.objectCollectionFromList([body for body in list(centerCutoutPattern.bodies) if not body.name == centerCutoutBody.name]),
            targetComponent,
        )
        extraCutoutBodies.append(centerCutoutBody)
        if input.hasConnectionHoles:
            connectionHoleFaceY = min([face for face in centerCutoutBody.faces if faceUtils.isYNormal(face)], key=lambda x: x.boundingBox.minPoint.y)
            connectionHoleYTool = createConnectionHoleTool(connectionHoleFaceY, input.connectionScrewHolesDiameter / 2, input.baseWidth / 2, targetComponent)
            connectionHoleFaceX = min([face for face in centerCutoutBody.faces if faceUtils.isXNormal(face)], key=lambda x: x.boundingBox.minPoint.x)
            connectionHoleXTool = createConnectionHoleTool(connectionHoleFaceX, input.connectionScrewHolesDiameter / 2, input.baseWidth / 2, targetComponent)

    holeCuttingBodies: list[adsk.fusion.BRepBody] = []
    
    if input.hasExtendedBottom and input.hasMagnetCutouts:
        magnetSocketBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(baseBody),
            0,
            input.magnetCutoutsDepth,
            input.magnetCutoutsDiameter / 2,
            holeCenterPoint,
            targetComponent,
        )
        holeCuttingBodies.append(magnetSocketBody)
    
    if input.hasExtendedBottom and input.hasScrewHoles:
        screwHoleBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(baseBody),
            0,
            input.bottomExtensionHeight,
            input.screwHolesDiameter / 2,
            holeCenterPoint,
            targetComponent,
        )
        holeCuttingBodies.append(screwHoleBody)

        screwHeadHeight = const.DIMENSION_SCREW_HEAD_CUTOUT_OFFSET_HEIGHT + (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2
        screwHeadBody = shapeUtils.simpleCylinder(
            faceUtils.getBottomFace(screwHoleBody),
            -screwHeadHeight,
            screwHeadHeight,
            input.screwHeadCutoutDiameter / 2,
            holeCenterPoint,
            targetComponent,
        )
        filletUtils.createChamfer(
            commonUtils.objectCollectionFromList(faceUtils.getTopFace(screwHeadBody).edges),
            (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2,
            targetComponent,
        )
        holeCuttingBodies.append(screwHeadBody)

    if len(holeCuttingBodies) > 0:
        patternSpacingX = input.baseWidth - const.DIMENSION_SCREW_HOLES_OFFSET * 2
        patternSpacingY = input.baseLength - const.DIMENSION_SCREW_HOLES_OFFSET * 2
        magnetScrewCutoutsPattern = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(holeCuttingBodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (patternSpacingX, patternSpacingY),
            (2, 2),
            targetComponent
        )
        extraCutoutBodies = extraCutoutBodies + holeCuttingBodies + list(magnetScrewCutoutsPattern.bodies)

    if len(extraCutoutBodies) > 0:
        combineUtils.joinBodies(
            baseBody,
            commonUtils.objectCollectionFromList(extraCutoutBodies),
            targetComponent,
        )
    
    # replicate base in rectangular pattern
    rectangularPatternFeatures: adsk.fusion.RectangularPatternFeatures = features.rectangularPatternFeatures
    patternInputBodies = adsk.core.ObjectCollection.create()
    patternInputBodies.add(baseBody)
    patternInput = rectangularPatternFeatures.createInput(patternInputBodies,
        targetComponent.xConstructionAxis,
        toValueInput(input.baseplateWidth),
        toValueInput(input.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    patternInput.directionTwoEntity = targetComponent.yConstructionAxis
    patternInput.quantityTwo = toValueInput(input.baseplateLength)
    patternInput.distanceTwo = toValueInput(input.baseLength)
    rectangularPattern = rectangularPatternFeatures.add(patternInput)
    cuttingTools = cuttingTools + list(rectangularPattern.bodies)
    return (cuttingTools, connectionHoleYTool, connectionHoleXTool)

def createSkeletonCutout(
    input: BaseplateGeneratorInput,
    bottomFace: adsk.fusion.BRepFace,
    holeCenterPoint: DimPoint,
    targetComponent: adsk.fusion.Component,
    joinInto: adsk.fusion.BRepBody = None,
):
    """One quarter of the skeletonized bottom cutout under a base pocket, sketched on the pocket's
    bottom face. A new body, or with `joinInto` joined into that body. Returns the extrude and
    the sketch point at the base centre (the axis for the 4x circular pattern)."""
    centerCutoutSketch,centerCutoutSketchCircle = baseGenerator.createCircleAtPointSketch(
        bottomFace,
        input.magnetCutoutsDiameter / 2,
        holeCenterPoint,
        targetComponent
    )
    centerCutoutSketch.name = "center bottom cutout"
    sketchUtils.convertToConstruction(centerCutoutSketch.sketchCurves)
    sketchCurves = centerCutoutSketch.sketchCurves
    dimensions = centerCutoutSketch.sketchDimensions
    constraints = centerCutoutSketch.geometricConstraints
    sketchLines = sketchCurves.sketchLines
    screwHoleCircle = sketchCurves.sketchCircles.item(0)
    arcRadius = dmax(input.magnetCutoutsDiameter, input.screwHeadCutoutDiameter) / 2 + 0.1
    arcStartingPoint = screwHoleCircle.centerSketchPoint.geometry.asVector()
    arcStartingPoint.add(adsk.core.Vector3D.create(0, float(arcRadius), 0))
    arc = sketchCurves.sketchArcs.addByCenterStartSweep(
        screwHoleCircle.centerSketchPoint,
        arcStartingPoint.asPoint(),
        math.radians(90),
    )

    verticalEdgeLine = min([line for line in sketchLines if sketchUtils.isVertical(line)], key=lambda x: abs(x.startSketchPoint.geometry.x))
    horizontalEdgeLine = min([line for line in sketchLines if sketchUtils.isHorizontal(line)], key=lambda x: abs(x.startSketchPoint.geometry.y))

    baseCenterOffsetX = input.baseWidth / 2 - input.xyClearance
    baseCenterOffsetY = input.baseLength / 2 - input.xyClearance
    line1 = sketchLines.addByTwoPoints(arc.startSketchPoint, adsk.core.Point3D.create(verticalEdgeLine.startSketchPoint.geometry.x, arc.startSketchPoint.geometry.y, 0))
    line2 = sketchLines.addByTwoPoints(line1.endSketchPoint, adsk.core.Point3D.create(line1.endSketchPoint.geometry.x, float(baseCenterOffsetY), 0))
    line3 = sketchLines.addByTwoPoints(line2.endSketchPoint, adsk.core.Point3D.create(-float(baseCenterOffsetX), float(baseCenterOffsetY), 0))
    line4 = sketchLines.addByTwoPoints(line3.endSketchPoint, adsk.core.Point3D.create(line3.endSketchPoint.geometry.x, horizontalEdgeLine.startSketchPoint.geometry.y, 0))
    line5 = sketchLines.addByTwoPoints(line4.endSketchPoint, adsk.core.Point3D.create(arc.endSketchPoint.geometry.x, line4.endSketchPoint.geometry.y, 0))
    line6 = sketchLines.addByTwoPoints(line5.endSketchPoint, arc.endSketchPoint)

    constraints.addCoincident(line1.endSketchPoint, verticalEdgeLine)
    constraints.addCoincident(line6.startSketchPoint, horizontalEdgeLine)
    constraints.addCoincident(screwHoleCircle.centerSketchPoint, arc.centerSketchPoint)
    constraints.addHorizontal(line1)
    constraints.addPerpendicular(line1, line2)
    constraints.addPerpendicular(line2, line3)
    constraints.addPerpendicular(line3, line4)
    constraints.addPerpendicular(line4, line5)
    constraints.addPerpendicular(line5, line6)
    constraints.addTangent(arc, line1)
    constraints.addEqual(line1, line6)
    constraints.addEqual(line2, line5)
    arcRadiusDimension = dimensions.addRadialDimension(arc, arc.endSketchPoint.geometry, True)
    applyExpression(arcRadiusDimension, arcRadius)
    cutoutWidthDimension = dimensions.addDistanceDimension(
        arc.endSketchPoint,
        line3.endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        line2.endSketchPoint.geometry
        )
    # From the arc end to the base centre. Driven explicitly: left to the sketch solver, a base
    # other than 42 mm put the cutout corner 1 mm past the base centre (upstream behaviour),
    # so the four cutouts overlapped; at 42 mm the value is unchanged.
    cutoutWidthDimension.parameter.expression = (baseCenterOffsetX - holeCenterPoint.x - arcRadius).expr

    centerCutoutExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
        centerCutoutSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation if joinInto is not None else adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.bottomExtensionHeight,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [joinInto] if joinInto is not None else [],
        targetComponent,
    )
    return (centerCutoutExtrudeFeature, line3.endSketchPoint)

def createPocketToolPattern(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component) -> adsk.fusion.BRepBody:
    """All base pockets (and their skeleton / magnet / screw cutouts) as one tool body whose cell
    count follows the plate count expressions.

    Same approach as the bin bases (see baseGenerator.createBaseFeaturePattern): every pocket feature
    joins a thin carrier plate (above the plate top, where it cuts nothing), repeated by a feature
    pattern with no bodies, fillets or chamfers of its own. The plate is then cut once with the
    carrier, one body for any count."""
    xyClearance = input.xyClearance
    holeOffset = const.DIMENSION_SCREW_HOLES_OFFSET
    cutoutInput = BaseGeneratorInput()
    cutoutInput.xyClearance = xyClearance
    cutoutInput.originPoint = DimPoint(-xyClearance * 2, -xyClearance * 2, 0)
    cutoutInput.baseWidth = input.baseWidth + xyClearance * 2
    cutoutInput.baseLength = input.baseLength + xyClearance * 2
    cutoutInput.cornerFilletRadius = input.cornerFilletRadius + xyClearance

    carrierInset = baseGenerator.BASE_CARRIER_INSET
    carrierExtrude = extrudeUtils.createBoxAtPoint(
        input.baseplateWidth * input.baseWidth - xyClearance * 2 - carrierInset * 2,
        input.baseplateLength * input.baseLength - xyClearance * 2 - carrierInset * 2,
        baseGenerator.BASE_CARRIER_THICKNESS,
        targetComponent,
        DimPoint(carrierInset, carrierInset, 0),
    )
    carrierExtrude.name = 'Pocket tool carrier'
    carrier = carrierExtrude.bodies.item(0)
    carrier.name = 'Pocket tool'

    design = targetComponent.parentDesign
    firstIndex = design.timeline.count
    baseGenerator.createSingleGridfinityBaseBody(cutoutInput, targetComponent, combineInto=carrier, combine=combineUtils.joinBodies)
    # the pocket bottom is the lowest face so far; a plane made from it outlives later joins there
    bottomFace = faceUtils.getBottomFace(carrier)
    bottomPlaneInput = targetComponent.constructionPlanes.createInput()
    bottomPlaneInput.setByOffset(bottomFace, adsk.core.ValueInput.createByReal(0))
    bottomPlane = targetComponent.constructionPlanes.add(bottomPlaneInput)
    bottomPlane.name = 'Pocket bottom plane'
    bottomPlane.isLightBulbOn = False
    holeCenterPoint = DimPoint(holeOffset - xyClearance, holeOffset - xyClearance, 0)

    if input.hasSkeletonizedBottom:
        skeletonStart = design.timeline.count
        createSkeletonCutout(input, bottomFace, holeCenterPoint, targetComponent, joinInto=carrier)
        skeletonFeatures = baseGenerator.timelineFeaturesSince(design, skeletonStart)
        centerAxis = createVerticalAxis(input.baseWidth / 2 - xyClearance, input.baseLength / 2 - xyClearance, 'Pocket centre', targetComponent)
        skeletonPatternInput = targetComponent.features.circularPatternFeatures.createInput(commonUtils.objectCollectionFromList(skeletonFeatures), centerAxis)
        skeletonPatternInput.quantity = adsk.core.ValueInput.createByString('4')
        skeletonPatternInput.patternComputeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
        targetComponent.features.circularPatternFeatures.add(skeletonPatternInput).name = 'Skeleton cutout pattern'

    if input.hasExtendedBottom and (input.hasMagnetCutouts or input.hasScrewHoles):
        holesStart = design.timeline.count
        if input.hasMagnetCutouts:
            shapeUtils.simpleCylinder(bottomPlane, 0, input.magnetCutoutsDepth, input.magnetCutoutsDiameter / 2, holeCenterPoint, targetComponent, joinInto=carrier)
        if input.hasScrewHoles:
            shapeUtils.simpleCylinder(bottomPlane, 0, input.bottomExtensionHeight, input.screwHolesDiameter / 2, holeCenterPoint, targetComponent, joinInto=carrier)
            # screw head: a short cylinder at the bottom, then a 45 degree countersink up to the screw
            # hole (upstream: a cylinder with its top edge chamfered)
            countersink = (input.screwHeadCutoutDiameter - input.screwHolesDiameter) / 2
            headStraight = const.DIMENSION_SCREW_HEAD_CUTOUT_OFFSET_HEIGHT
            shapeUtils.simpleCylinder(bottomPlane, input.bottomExtensionHeight - headStraight, headStraight,
                input.screwHeadCutoutDiameter / 2, holeCenterPoint, targetComponent, joinInto=carrier)
            shapeUtils.simpleCylinder(bottomPlane, input.bottomExtensionHeight - headStraight, -countersink,
                input.screwHeadCutoutDiameter / 2, holeCenterPoint, targetComponent, joinInto=carrier, taperAngle='-45 deg')
        holeFeatures = baseGenerator.timelineFeaturesSince(design, holesStart)
        holesPatternInput = targetComponent.features.rectangularPatternFeatures.createInput(commonUtils.objectCollectionFromList(holeFeatures),
            targetComponent.xConstructionAxis,
            adsk.core.ValueInput.createByString('2'),
            toValueInput(input.baseWidth - holeOffset * 2),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        holesPatternInput.directionTwoEntity = targetComponent.yConstructionAxis
        holesPatternInput.quantityTwo = adsk.core.ValueInput.createByString('2')
        holesPatternInput.distanceTwo = toValueInput(input.baseLength - holeOffset * 2)
        holesPatternInput.patternComputeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
        targetComponent.features.rectangularPatternFeatures.add(holesPatternInput).name = 'Magnet and screw holes pattern'

    pocketFeatures = baseGenerator.timelineFeaturesSince(design, firstIndex)
    pocketPatternInput = targetComponent.features.rectangularPatternFeatures.createInput(commonUtils.objectCollectionFromList(pocketFeatures),
        targetComponent.xConstructionAxis,
        toValueInput(input.baseplateWidth),
        toValueInput(input.baseWidth),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    pocketPatternInput.directionTwoEntity = targetComponent.yConstructionAxis
    pocketPatternInput.quantityTwo = toValueInput(input.baseplateLength)
    pocketPatternInput.distanceTwo = toValueInput(input.baseLength)
    pocketPatternInput.patternComputeOption = adsk.fusion.PatternComputeOptions.AdjustPatternCompute
    targetComponent.features.rectangularPatternFeatures.add(pocketPatternInput).name = 'Pocket pattern'
    return carrier

def createVerticalAxis(x, y, name: str, targetComponent: adsk.fusion.Component):
    """Hidden construction axis parallel to Z through (x, y); follows x/y when they are Dims."""
    planes = targetComponent.constructionPlanes
    xzPlaneInput = planes.createInput()
    xzPlaneInput.setByOffset(targetComponent.xZConstructionPlane, toValueInput(y))
    xzPlane = planes.add(xzPlaneInput)
    xzPlane.isLightBulbOn = False
    yzPlaneInput = planes.createInput()
    yzPlaneInput.setByOffset(targetComponent.yZConstructionPlane, toValueInput(x))
    yzPlane = planes.add(yzPlaneInput)
    yzPlane.isLightBulbOn = False
    axisInput = targetComponent.constructionAxes.createInput()
    axisInput.setByTwoPlanes(xzPlane, yzPlane)
    axis = targetComponent.constructionAxes.add(axisInput)
    axis.name = f"{name} axis"
    axis.isLightBulbOn = False
    return axis

def createGridfinityBaseplate(input: BaseplateGeneratorInput, targetComponent: adsk.fusion.Component):
    features = targetComponent.features
    if isParametric(input.baseplateWidth, input.baseplateLength):
        cuttingTools = [createPocketToolPattern(input, targetComponent)]
        connectionHoleYTool = None
        connectionHoleXTool = None
    else:
        cuttingTools, connectionHoleYTool, connectionHoleXTool = createPocketToolBodies(input, targetComponent)

    # create baseplate body
    baseplateTrueWidth = input.baseplateWidth * input.baseWidth - input.xyClearance * 2
    baseplateTrueLength = input.baseplateLength * input.baseLength - input.xyClearance * 2
    binInterfaceBody = shapeUtils.simpleBox(
        targetComponent.xYConstructionPlane,
        0,
        input.baseplateWidth * input.baseWidth - input.xyClearance * 2,
        input.baseplateLength * input.baseLength - input.xyClearance * 2,
        -const.BIN_BASE_HEIGHT,
        targetComponent.originConstructionPoint.geometry,
        targetComponent,
    )

    if input.binZClearance > 0:
        binZClearance = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                0,
                baseplateTrueWidth + input.paddingLeft + input.paddingRight,
                baseplateTrueLength + input.paddingBottom + input.paddingTop,
                -input.binZClearance,
                geometryUtils.createOffsetPoint(
                    targetComponent.originConstructionPoint.geometry,
                    byX=-input.paddingLeft,
                    byY=-input.paddingBottom
                ),
                targetComponent
            )
        binZClearance.name = "Top negative volume"
        cuttingTools.append(binZClearance)

    if input.hasPadding:
        paddingHeigth = const.BIN_BASE_HEIGHT
        mergeTools = []
        if input.paddingLeft > 0:
            paddingLeftBody = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                0,
                input.paddingLeft,
                baseplateTrueLength + input.paddingBottom + input.paddingTop,
                -paddingHeigth,
                geometryUtils.createOffsetPoint(
                    targetComponent.originConstructionPoint.geometry,
                    byX=-input.paddingLeft,
                    byY=-input.paddingBottom
                ),
                targetComponent
            )
            paddingLeftBody.name = "Padding left"
            mergeTools.append(paddingLeftBody)
        if input.paddingTop > 0:
            paddingTopBody = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                0,
                baseplateTrueWidth + input.paddingLeft + input.paddingRight,
                input.paddingTop,
                -paddingHeigth,
                geometryUtils.createOffsetPoint(
                    targetComponent.originConstructionPoint.geometry,
                    byX=-input.paddingLeft,
                    byY=baseplateTrueLength
                ),
                targetComponent
            )
            paddingTopBody.name = "Padding top"
            mergeTools.append(paddingTopBody)
        if input.paddingRight > 0:
            paddingRightBody = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                0,
                input.paddingRight,
                baseplateTrueLength + input.paddingTop + input.paddingBottom,
                -paddingHeigth,
                geometryUtils.createOffsetPoint(
                    targetComponent.originConstructionPoint.geometry,
                    byX=baseplateTrueWidth,
                    byY=-input.paddingBottom
                ),
                targetComponent
            )
            paddingRightBody.name = "Padding right"
            mergeTools.append(paddingRightBody)
        if input.paddingBottom > 0:
            paddingBottomBody = shapeUtils.simpleBox(
                targetComponent.xYConstructionPlane,
                0,
                baseplateTrueWidth + input.paddingLeft + input.paddingRight,
                input.paddingBottom,
                -paddingHeigth,
                geometryUtils.createOffsetPoint(
                    targetComponent.originConstructionPoint.geometry,
                    byX=-input.paddingLeft,
                    byY=-input.paddingBottom
                ),
                targetComponent
            )
            paddingBottomBody.name = "Padding bottom"
            mergeTools.append(paddingBottomBody)
        if len(mergeTools) > 0:
            paddingCombineFeature = combineUtils.joinBodies(
                binInterfaceBody,
                commonUtils.objectCollectionFromList(mergeTools),
                targetComponent,
            )
            paddingCombineFeature.name = "Combine base with padding bodies"
            binInterfaceBody = paddingCombineFeature.bodies.item(0)

    cornerFillet = filletUtils.filletEdgesByLength(
        binInterfaceBody.faces,
        input.cornerFilletRadius - input.xyClearance,
        const.BIN_BASE_HEIGHT,
        targetComponent,
        )
    cornerFillet.name = "Round outer corners"
    
    if input.hasExtendedBottom:
        baseplateBottomLayer = extrudeUtils.simpleDistanceExtrude(
            faceUtils.getBottomFace(binInterfaceBody),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            input.bottomExtensionHeight,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
            [],
            targetComponent,
        )
        baseplateBottomLayerBody = baseplateBottomLayer.bodies.item(0)
        combineUtils.joinBodies(binInterfaceBody, commonUtils.objectCollectionFromList([baseplateBottomLayerBody]), targetComponent)

    bottomChamfer = filletUtils.chamferEdgesByLength(
        [faceUtils.getBottomFace(binInterfaceBody)],
        0.05,
        baseplateTrueLength + (input.paddingTop + input.paddingBottom if input.hasPadding else 0),
        const.BIN_CORNER_FILLET_RADIUS * 3,
        targetComponent,
    )
    bottomChamfer.name = "Bottom chamfer"

    if not connectionHoleYTool is None and not connectionHoleXTool is None:
        holeToolsXFeature = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(connectionHoleXTool.bodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (input.baseWidth, input.baseLength),
            (1, input.baseplateLength),
            targetComponent
        )
        connectionHoleXToolList = list(connectionHoleXTool.bodies) + list(holeToolsXFeature.bodies)

        holeToolsYFeature = patternUtils.recPattern(
            commonUtils.objectCollectionFromList(connectionHoleYTool.bodies),
            (targetComponent.xConstructionAxis, targetComponent.yConstructionAxis),
            (input.baseLength, input.baseLength),
            (input.baseplateWidth, 1),
            targetComponent
        )
        connectionHoleYToolList = list(connectionHoleYTool.bodies) + list(holeToolsYFeature.bodies)

        constructionPlaneXZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneXZInput.setByOffset(targetComponent.xZConstructionPlane, toValueInput(input.baseplateLength * input.baseLength / 2 - input.xyClearance))
        constructionPlaneXZ = targetComponent.constructionPlanes.add(constructionPlaneXZInput)
        constructionPlaneXZ.isLightBulbOn = False

        constructionPlaneYZInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
        constructionPlaneYZInput.setByOffset(targetComponent.yZConstructionPlane, toValueInput(input.baseplateWidth * input.baseWidth / 2 - input.xyClearance))
        constructionPlaneYZ = targetComponent.constructionPlanes.add(constructionPlaneYZInput)
        constructionPlaneYZ.isLightBulbOn = False

        mirrorConnectionHolesYZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleXToolList), constructionPlaneYZ)
        mirrorConnectionHolesYZ = features.mirrorFeatures.add(mirrorConnectionHolesYZInput)

        mirrorConnectionHolesXZInput = features.mirrorFeatures.createInput(commonUtils.objectCollectionFromList(connectionHoleYToolList), constructionPlaneXZ)
        mirrorConnectionHolesXZ = features.mirrorFeatures.add(mirrorConnectionHolesXZInput)

        cuttingTools = cuttingTools + list(mirrorConnectionHolesYZ.bodies) + list(mirrorConnectionHolesXZ.bodies) + connectionHoleYToolList + connectionHoleXToolList


    # cut everything
    toolBodies = commonUtils.objectCollectionFromList(cuttingTools)
    finalCut = combineUtils.cutBody(
        binInterfaceBody,
        toolBodies,
        targetComponent,
    )
    finalCut.name = "Final baseplate cut"

    return binInterfaceBody

def createConnectionHoleTool(connectionHoleFace: adsk.fusion.BRepFace, diameter: float, depth: float, targetComponent: adsk.fusion.Component):
    connectionHoleSketch: adsk.fusion.Sketch = targetComponent.sketches.add(connectionHoleFace)
    connectionHoleSketch.name = "side connector hole"
    sketchCurves = connectionHoleSketch.sketchCurves
    dimensions = connectionHoleSketch.sketchDimensions
    constraints = connectionHoleSketch.geometricConstraints
    sketchUtils.convertToConstruction(sketchCurves)
    [sketchHorizontalEdge1, sketchHorizontalEdge2] = [line for line in sketchCurves.sketchLines if sketchUtils.isHorizontal(line)]
    line1 = sketchCurves.sketchLines.addByTwoPoints(sketchHorizontalEdge1.startSketchPoint.geometry, sketchHorizontalEdge2.endSketchPoint.geometry)
    line1.isConstruction = True
    constraints.addMidPoint(line1.startSketchPoint, sketchHorizontalEdge1)
    constraints.addMidPoint(line1.endSketchPoint, sketchHorizontalEdge2)
    
    circle = sketchCurves.sketchCircles.addByCenterRadius(
        connectionHoleSketch.originPoint.geometry,
        float(diameter)
    )
    constraints.addMidPoint(circle.centerSketchPoint, line1)
    applyExpression(dimensions.addRadialDimension(circle, line1.startSketchPoint.geometry, True), diameter)
    connectionHoleTool = extrudeUtils.simpleDistanceExtrude(
        connectionHoleSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        depth,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    return connectionHoleTool