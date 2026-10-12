import adsk.core, adsk.fusion, traceback
import os

from . import extrudeUtils, sketchUtils
from .dim import toValueInput, applyExpression

app = adsk.core.Application.get()
ui = app.userInterface

def simpleCylinder(
    plane: adsk.core.Base,
    planeOffset: float,
    height: float,
    radius: float,
    centerBottom: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    baseConstructionPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    baseConstructionPlaneInput.setByOffset(plane, toValueInput(planeOffset))
    baseConstructionPlane = targetComponent.constructionPlanes.add(baseConstructionPlaneInput)
    cylinderBaseSketch: adsk.fusion.Sketch = targetComponent.sketches.add(baseConstructionPlane)
    cylinderBaseSketch.name = "Simple cylinder sketch"
    dimensions: adsk.fusion.SketchDimensions = cylinderBaseSketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = cylinderBaseSketch.geometricConstraints
    centerOnSketch = sketchUtils.modelToSketch(cylinderBaseSketch, centerBottom)
    centerPoint = adsk.core.Point3D.create(float(centerOnSketch.x), float(centerOnSketch.y), 0)

    circle = cylinderBaseSketch.sketchCurves.sketchCircles.addByCenterRadius(
        centerPoint,
        float(radius),
    )
    diameterDimension = dimensions.addDiameterDimension(
        circle,
        adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x + 1, circle.centerSketchPoint.geometry.y + 1, 0),
        True,
    )
    applyExpression(diameterDimension, radius * 2)
    if centerPoint.isEqualTo(cylinderBaseSketch.originPoint.geometry):
        constraints.addCoincident(cylinderBaseSketch.originPoint, circle.centerSketchPoint)
    else:
        centerXDimension = dimensions.addDistanceDimension(
            cylinderBaseSketch.originPoint,
            circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            adsk.core.Point3D.create(circle.centerSketchPoint.geometry.x, 0, 0),
            True
        )
        centerYDimension = dimensions.addDistanceDimension(
            cylinderBaseSketch.originPoint,
            circle.centerSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            adsk.core.Point3D.create(0, circle.centerSketchPoint.geometry.y, 0),
            True
        )
        applyExpression(centerXDimension, centerOnSketch.x)
        applyExpression(centerYDimension, centerOnSketch.y)
    
    cylinderExtrude = extrudeUtils.simpleDistanceExtrude(
        cylinderBaseSketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        height,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
        [],
        targetComponent,
    )
    cylinderExtrude.name = "Simple cylinder extrude"
    return cylinderExtrude.bodies.item(0)

def simpleBox(
    plane: adsk.core.Base,
    planeOffset: float,
    width: float,
    length: float,
    height: float,
    originPoint: adsk.core.Point3D,
    targetComponent: adsk.fusion.Component,
):
    features: adsk.fusion.Features = targetComponent.features
    extrudeFeatures: adsk.fusion.ExtrudeFeatures = features.extrudeFeatures
    boxPlaneInput: adsk.fusion.ConstructionPlaneInput = targetComponent.constructionPlanes.createInput()
    boxPlaneInput.setByOffset(
        plane,
        toValueInput(planeOffset)
    )
    boxConstructionPlane = targetComponent.constructionPlanes.add(boxPlaneInput)
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    recSketch: adsk.fusion.Sketch = sketches.add(boxConstructionPlane)
    recSketch.name = "Simple box sketch"
    sketchUtils.createRectangle(width, length, sketchUtils.modelToSketch(recSketch, originPoint), recSketch)
        
    # extrude
    extrude = extrudeFeatures.addSimple(recSketch.profiles.item(0),
        toValueInput(height),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude.name = "Simple box extrude"
    return extrude.bodies.item(0)