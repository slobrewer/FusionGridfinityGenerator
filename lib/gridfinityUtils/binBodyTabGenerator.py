import adsk.core, adsk.fusion, traceback
import os
import math



from .const import BIN_TAB_EDGE_FILLET_RADIUS
from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyTabGeneratorInput import BinBodyTabGeneratorInput
from ... import config
from .dim import toValueInput, applyExpression

app = adsk.core.Application.get()
ui = app.userInterface

def getInnerCutoutScoopFace(
    innerCutout: adsk.fusion.BRepBody
    ) -> tuple[adsk.fusion.BRepFace, adsk.fusion.BRepFace]:
    innerCutoutYNormalFaces = [face for face in innerCutout.faces if faceUtils.isYNormal(face)]
    scoopFace = min(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    oppositeFace = max(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    return (scoopFace, oppositeFace)

def createGridfinityBinBodyTab(
    input: BinBodyTabGeneratorInput,
    targetComponent: adsk.fusion.Component,
):

    tabProfilePlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    tabProfilePlaneInput.setByOffset(
        targetComponent.yZConstructionPlane,
        toValueInput(input.origin.x)
        )
    tabProfilePlane = targetComponent.constructionPlanes.add(tabProfilePlaneInput)
    tabSketch: adsk.fusion.Sketch = targetComponent.sketches.add(tabProfilePlane)
    tabSketch.name = "label tab sketch"
    tabSketchLine = tabSketch.sketchCurves.sketchLines
    tabTopEdgeHeight = input.origin.z - input.topClearance
    originX, originY, topEdgeZ = float(input.origin.x), float(input.origin.y), float(tabTopEdgeHeight)
    actualTabWidth = input.width + BIN_TAB_EDGE_FILLET_RADIUS / math.tan((math.radians(90) - input.overhangAngle) / 2)
    actualTabHeight = actualTabWidth / math.tan(input.overhangAngle)
    line1 = tabSketchLine.addByTwoPoints(
        tabSketch.modelToSketchSpace(adsk.core.Point3D.create(originX, originY, topEdgeZ)),
        tabSketch.modelToSketchSpace(adsk.core.Point3D.create(originX, originY, topEdgeZ - actualTabHeight)),
    )
    line2 = tabSketchLine.addByTwoPoints(
        tabSketch.modelToSketchSpace(adsk.core.Point3D.create(originX, originY, topEdgeZ)),
        tabSketch.modelToSketchSpace(adsk.core.Point3D.create(originX, originY - actualTabWidth, topEdgeZ)),
    )
    line3 = tabSketchLine.addByTwoPoints(
        tabSketch.modelToSketchSpace(adsk.core.Point3D.create(originX, originY, topEdgeZ - actualTabHeight)),
        tabSketch.modelToSketchSpace(adsk.core.Point3D.create(originX, originY - actualTabWidth, topEdgeZ)),
    )

    constraints: adsk.fusion.GeometricConstraints = tabSketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = tabSketch.sketchDimensions

    # horizontal/vertical relative to local sketch XY coordinates
    constraints.addHorizontal(line1)
    constraints.addVertical(line2)
    constraints.addCoincident(line1.startSketchPoint, line2.startSketchPoint)
    constraints.addCoincident(line2.endSketchPoint, line3.endSketchPoint)
    constraints.addCoincident(line1.endSketchPoint, line3.startSketchPoint)

    originVerticalDimension = dimensions.addDistanceDimension(
        tabSketch.originPoint,
        line1.startSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        line1.startSketchPoint.geometry,
        True
        )

    originHorizontalDimension = dimensions.addDistanceDimension(
        tabSketch.originPoint,
        line1.startSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        line1.startSketchPoint.geometry,
        True
        )

    # link the tab's top edge height to the bin height; pick whichever sketch axis is model Z
    sketchXIsModelZ = abs(tabSketch.xDirection.z) > 0.5
    applyExpression(originHorizontalDimension if sketchXIsModelZ else originVerticalDimension, tabTopEdgeHeight)

    dimensions.addDistanceDimension(
        line2.startSketchPoint,
        line2.endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        line2.endSketchPoint.geometry,
        True
        )
            
    dimensions.addAngularDimension(
        line1,
        line3,
        line1.endSketchPoint.geometry,
        True,
        )

    tabExtrudeFeature = extrudeUtils.simpleDistanceExtrude(
        tabSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.length,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    tabBody = tabExtrudeFeature.bodies.item(0)
    tabBody.name = 'label tab'

    tabTopFace = faceUtils.getTopFace(tabBody)
    roundedEdge = min([edge for edge in tabTopFace.edges if geometryUtils.isCollinearToX(edge)], key=lambda x: x.boundingBox.minPoint.y)
    fillet = filletUtils.createFillet(
        [roundedEdge],
        BIN_TAB_EDGE_FILLET_RADIUS,
        False,
        targetComponent
    )
    fillet.name = 'label tab fillet'

    return tabBody
