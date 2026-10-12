import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, geometryUtils
from .dim import DimPoint, applyExpression, asPoint3D, isParametric

def isVertical(line: adsk.fusion.SketchLine):
    return math.isclose(line.startSketchPoint.geometry.x, line.endSketchPoint.geometry.x, abs_tol=const.DEFAULT_FILTER_TOLERANCE)

def isHorizontal(line: adsk.fusion.SketchLine):
    return math.isclose(line.startSketchPoint.geometry.y, line.endSketchPoint.geometry.y, abs_tol=const.DEFAULT_FILTER_TOLERANCE)

def modelToSketch(sketch: adsk.fusion.Sketch, point):
    """Sketch-space position of a model point, keeping Dim coordinates when the point is parametric.
    Sketches on planes parallel to the origin planes (and on such faces) have their origin at the
    projected model origin and axes along +/- model axes, so each sketch coordinate is +/- one
    model coordinate."""
    if not isParametric(point.x, point.y, point.z):
        return geometryUtils.pointToXY(sketch.modelToSketchSpace(asPoint3D(point)))
    modelCoordinates = [point.x, point.y, point.z]
    origin = sketch.origin.asArray()
    sketchCoordinates = []
    for direction in (sketch.xDirection.asArray(), sketch.yDirection.asArray()):
        axis = max(range(3), key=lambda i: abs(direction[i]))
        if abs(abs(direction[axis]) - 1) > const.DEFAULT_FILTER_TOLERANCE:
            # tilted sketch: no simple expression, fall back to the current value
            return geometryUtils.pointToXY(sketch.modelToSketchSpace(asPoint3D(point)))
        coordinate = modelCoordinates[axis] - origin[axis]
        sketchCoordinates.append(coordinate if direction[axis] > 0 else -coordinate)
    return DimPoint(sketchCoordinates[0], sketchCoordinates[1], 0)

def createRectangle(
    width: float,
    length: float,
    startPoint: adsk.core.Point3D,
    sketch: adsk.fusion.Sketch,
):
    """Rectangle from `startPoint` (sketch space) along +x/+y. Width, length and the start point
    coordinates may be Dims; the matching sketch dimensions then follow their expressions."""
    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    dimensions: adsk.fusion.SketchDimensions = sketch.sketchDimensions
    lines: adsk.fusion.SketchLines = sketch.sketchCurves.sketchLines
    startX, startY = float(startPoint.x), float(startPoint.y)
    rectangleLines = lines.addTwoPointRectangle(
        adsk.core.Point3D.create(startX, startY, 0),
        adsk.core.Point3D.create(startX + float(width), startY + float(length), 0)
    )
    constraints.addHorizontal(rectangleLines.item(0))
    constraints.addVertical(rectangleLines.item(1))
    constraints.addHorizontal(rectangleLines.item(2))
    constraints.addVertical(rectangleLines.item(3))
    if adsk.core.Point3D.create(startX, startY, 0).isEqualTo(sketch.originPoint.geometry):
        constraints.addCoincident(sketch.originPoint, rectangleLines.item(3))
        constraints.addCoincident(sketch.originPoint, rectangleLines.item(0))
    else:
        startYDimension = dimensions.addDistanceDimension(
            sketch.originPoint,
            rectangleLines.item(0).startSketchPoint,
            adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
            rectangleLines.item(0).startSketchPoint.geometry,
            True,
        )
        startXDimension = dimensions.addDistanceDimension(
            sketch.originPoint,
            rectangleLines.item(3).startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            rectangleLines.item(3).startSketchPoint.geometry,
            True,
        )
        applyExpression(startYDimension, startPoint.y)
        applyExpression(startXDimension, startPoint.x)
    widthDimension = dimensions.addDistanceDimension(rectangleLines.item(0).startSketchPoint,
        rectangleLines.item(0).endSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        rectangleLines.item(0).endSketchPoint.geometry)
    lengthDimension = dimensions.addDistanceDimension(rectangleLines.item(1).startSketchPoint,
        rectangleLines.item(1).endSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
        rectangleLines.item(1).endSketchPoint.geometry)
    applyExpression(widthDimension, width)
    applyExpression(lengthDimension, length)
    return rectangleLines

def filterCirclesByRadius(
    radius: float,
    tolerance: float,
    sketchCircles: adsk.fusion.SketchCircles,
):
    filteredCircles = []
    for circle in sketchCircles:
        if abs (circle.radius - radius) < tolerance:
            filteredCircles.append(circle)

    return filteredCircles

def createOffsetProfileSketch(
    planarEntity: adsk.core.Base,
    offsetValue: float,
    targetComponent: adsk.fusion.Component,
):
    sketches: adsk.fusion.Sketches = targetComponent.sketches
    sketch: adsk.fusion.Sketch = sketches.add(planarEntity)
    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    curvesList: list[adsk.fusion.SketchCurve] = []
    for curve in sketch.sketchCurves:
        curvesList.append(curve)
        curve.isConstruction = True
    constraints.addOffset(curvesList,
        adsk.core.ValueInput.createByReal(offsetValue),
        sketch.sketchCurves.sketchLines.item(0).startSketchPoint.geometry)

    return sketch

def convertToConstruction(curves: adsk.fusion.SketchCurves):
    for curve in curves:
        curve.isConstruction = True
