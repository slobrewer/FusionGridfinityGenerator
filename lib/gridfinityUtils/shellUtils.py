import adsk.core, adsk.fusion, traceback
import os

from .dim import toValueInput


def simpleShell(
    openFaces: list[adsk.fusion.BRepFace],
    thickness: float,
    targetComponent: adsk.fusion.Component,
    ):
    shellFeatures = targetComponent.features.shellFeatures
    shellBinObjects = adsk.core.ObjectCollection.create()
    for face in openFaces:
        shellBinObjects.add(face)
    shellBinInput = shellFeatures.createInput(shellBinObjects, False)
    shellBinInput.insideThickness = toValueInput(thickness)
    return shellFeatures.add(shellBinInput)