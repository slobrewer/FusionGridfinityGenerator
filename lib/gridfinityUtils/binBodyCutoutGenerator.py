import adsk.core, adsk.fusion, traceback
import os
import math

from ...lib.gridfinityUtils import geometryUtils
from ...lib import fusion360utils as futil
from ...lib.gridfinityUtils import filletUtils
from . import const, combineUtils, faceUtils, commonUtils, sketchUtils, extrudeUtils, baseGenerator, edgeUtils
from .baseGeneratorInput import BaseGeneratorInput
from .binBodyCutoutGeneratorInput import BinBodyCutoutGeneratorInput
from ... import config
from .dim import toValueInput, dmax, dmin, isParametric

app = adsk.core.Application.get()
ui = app.userInterface

def getInnerCutoutScoopFace(
    innerCutout: adsk.fusion.BRepBody
    ) -> tuple[adsk.fusion.BRepFace, adsk.fusion.BRepFace]:
    innerCutoutYNormalFaces = [face for face in innerCutout.faces if faceUtils.isYNormal(face)]
    scoopFace = min(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    oppositeFace = max(innerCutoutYNormalFaces, key=lambda x: x.boundingBox.minPoint.y)
    return (scoopFace, oppositeFace)

def createGridfinityBinBodyCutout(
    input: BinBodyCutoutGeneratorInput,
    targetComponent: adsk.fusion.Component,
):

    cutoutPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    cutoutPlaneInput.setByOffset(
        targetComponent.xYConstructionPlane,
        toValueInput(input.origin.z)
    )
    cutoutConstructionPlane = targetComponent.constructionPlanes.add(cutoutPlaneInput)
    innerCutoutSketch: adsk.fusion.Sketch = targetComponent.sketches.add(cutoutConstructionPlane)
    innerCutoutSketch.name = 'Inner cutout sketch'
    sketchUtils.createRectangle(
        input.width,
        input.length,
        sketchUtils.modelToSketch(innerCutoutSketch, input.origin),
        innerCutoutSketch,
    )

    innerCutout = extrudeUtils.simpleDistanceExtrude(
        innerCutoutSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        input.height,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
        [],
        targetComponent,
    )
    innerCutout.name = 'Inner cutout extrude'
    innerCutoutBody = innerCutout.bodies.item(0)
    innerCutoutBody.name = 'Inner cutout'

    # scoop
    if input.hasScoop:
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopEdge = faceUtils.getBottomHorizontalEdge(innerCutoutScoopFace.edges)
        scoopHeightLimit = input.height
        if isParametric(input.height):
            # a scoop as tall as the wall consumes the whole face and later fillets lose their
            # edges when the height changes; leaving a sliver of wall keeps the topology stable
            scoopHeightLimit = input.height - const.BIN_SCOOP_MIN_TOP_WALL
        scoopMaxRadius = dmax(dmin(input.scoopMaxRadius, scoopHeightLimit), input.filletRadius)
        filletUtils.createFillet(
            [scoopEdge],
            scoopMaxRadius,
            False,
            targetComponent
        )
    # fillet inner cutout
    [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
    innerCutoutVerticalFaces = faceUtils.getVerticalEdges(innerCutoutBody.faces)
    filletUtils.createFillet(
        innerCutoutVerticalFaces,
        input.filletRadius,
        True,
        targetComponent
    )
    if input.hasBottomFillet:
        # recalculate faces after fillet
        [innerCutoutScoopFace, innerCutoputScoopOppositeFace] = getInnerCutoutScoopFace(innerCutoutBody)
        scoopOppositeEdge = faceUtils.getBottomHorizontalEdge(innerCutoputScoopOppositeFace.edges)

        filletUtils.createFillet(
            [scoopOppositeEdge],
            input.filletRadius,
            True,
            targetComponent
        )

    return innerCutoutBody
