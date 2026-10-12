import math
import adsk.core, adsk.fusion, traceback
import os

from . import const, geometryUtils
from .dim import Dim, DimPoint, applyExpression, asPoint3D, isParametric

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

def _coordinateKey(value):
    return value.expr if isinstance(value, Dim) else round(float(value), 9)

def createRoundedRectangle(
    width,
    length,
    startPoint,
    radius,
    sketch: adsk.fusion.Sketch,
):
    """createRectangle with all four corners filleted to `radius` (equal radii, one radial
    dimension linked to `radius`)."""
    [side1, side2, side3, side4] = list(createRectangle(width, length, startPoint, sketch))
    arcs = sketch.sketchCurves.sketchArcs
    radiusValue = float(radius)
    fillet1 = arcs.addFillet(side1, side1.endSketchPoint.geometry, side2, side2.startSketchPoint.geometry, radiusValue)
    fillet2 = arcs.addFillet(side2, side2.endSketchPoint.geometry, side3, side3.startSketchPoint.geometry, radiusValue)
    fillet3 = arcs.addFillet(side3, side3.endSketchPoint.geometry, side4, side4.startSketchPoint.geometry, radiusValue)
    fillet4 = arcs.addFillet(side4, side4.endSketchPoint.geometry, side1, side1.startSketchPoint.geometry, radiusValue)
    constraints = sketch.geometricConstraints
    constraints.addEqual(fillet1, fillet2)
    constraints.addEqual(fillet2, fillet3)
    constraints.addEqual(fillet3, fillet4)
    applyExpression(sketch.sketchDimensions.addRadialDimension(fillet1, fillet1.startSketchPoint.geometry), radius)

def createPolygon(points: list, sketch: adsk.fusion.Sketch):
    """Closed polygon through `points` (sketch space, DimPoints allowed). Every vertex gets a
    horizontal and a vertical dimension from the sketch origin, linked to its expressions.

    Fusion reports a sketch as over constrained when two points get distance dimensions of the same
    value along the same axis, so a vertex that shares a coordinate expression with an earlier
    vertex is aligned to it (vertical / horizontal points constraint) instead."""
    dimensions: adsk.fusion.SketchDimensions = sketch.sketchDimensions
    constraints: adsk.fusion.GeometricConstraints = sketch.geometricConstraints
    lines: adsk.fusion.SketchLines = sketch.sketchCurves.sketchLines
    corners = [adsk.core.Point3D.create(float(point.x), float(point.y), 0) for point in points]
    polygonLines = []
    for index in range(len(corners)):
        start = polygonLines[-1].endSketchPoint if polygonLines else corners[0]
        end = polygonLines[0].startSketchPoint if index == len(corners) - 1 else corners[index + 1]
        polygonLines.append(lines.addByTwoPoints(start, end))
    dimensionedX = {}
    dimensionedY = {}
    for point, line in zip(points, polygonLines):
        vertex = line.startSketchPoint
        xKey, yKey = _coordinateKey(point.x), _coordinateKey(point.y)
        if xKey in dimensionedX:
            constraints.addVerticalPoints(dimensionedX[xKey], vertex)
        else:
            xDimension = dimensions.addDistanceDimension(
                sketch.originPoint,
                vertex,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(vertex.geometry.x, vertex.geometry.y + 0.5, 0),
                True,
            )
            applyExpression(xDimension, point.x)
            dimensionedX[xKey] = vertex
        if yKey in dimensionedY:
            constraints.addHorizontalPoints(dimensionedY[yKey], vertex)
        else:
            yDimension = dimensions.addDistanceDimension(
                sketch.originPoint,
                vertex,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                adsk.core.Point3D.create(vertex.geometry.x + 0.5, vertex.geometry.y, 0),
                True,
            )
            applyExpression(yDimension, point.y)
            dimensionedY[yKey] = vertex
    return polygonLines

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
