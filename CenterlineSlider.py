import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np
import time
#from pysinewave import SineWave

try:
  from pysinewave import SineWave
except: 
  slicer.util.pip_install('pysinewave')
  from pysinewave import SineWave

#global metricArray

#
# Centerline Audio Slider
#

class CenterlineSlider(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "CenterlineSlider"
    self.parent.categories = ["CenterlineSlider"]
    self.parent.dependencies = []
    self.parent.contributors = ["Rebecca Lisk"]
    self.parent.helpText = """
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
"""

#
# qSlicerPythonModuleExampleWidget
#

class CenterlineSliderWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.cameraNode = None
    self.cameraNodeObserverTag = None
    self.cameraObserverTag= None
    # Flythough variables
    self.transform = None
    self.path = None
    self.camera = None
    self.skip = 0
    self.timer = qt.QTimer()
    self.timer.setInterval(40)
    self.timer.connect('timeout()', self.flyToNext)


  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Path collapsible button
    pathCollapsibleButton = ctk.ctkCollapsibleButton()
    pathCollapsibleButton.text = "Path"
    self.layout.addWidget(pathCollapsibleButton)

    # Layout within the path collapsible button
    pathFormLayout = qt.QFormLayout(pathCollapsibleButton)

    # vtkpolydata centerline selector
    self.inputModelNodeSelector = slicer.qMRMLNodeComboBox()
    self.inputModelNodeSelector.objectName = 'inputModelNodeSelector'
    self.inputModelNodeSelector.toolTip = "Select the centerline input polydata."
    self.inputModelNodeSelector.nodeTypes = ['vtkMRMLModelNode']
    self.inputModelNodeSelector.hideChildNodeTypes = ['vtkMRMLAnnotationNode']  # hide all annotation nodes
    self.inputModelNodeSelector.noneEnabled = False
    self.inputModelNodeSelector.addEnabled = False
    self.inputModelNodeSelector.removeEnabled = False
    pathFormLayout.addRow("Centerline polydata:", self.inputModelNodeSelector)
    self.parent.connect('mrmlSceneChanged(vtkMRMLScene*)',
                        self.inputModelNodeSelector, 'setMRMLScene(vtkMRMLScene*)')

    # (Optional) vtk model selector
    self.optionalModelNodeSelector = slicer.qMRMLNodeComboBox()
    self.optionalModelNodeSelector.objectName = 'optionalModelNodeSelector'
    self.optionalModelNodeSelector.toolTip = "Select the input bronchus model."
    self.optionalModelNodeSelector.nodeTypes = ['vtkMRMLModelNode']
    self.optionalModelNodeSelector.hideChildNodeTypes = ['vtkMRMLAnnotationNode']  # hide all annotation nodes
    self.optionalModelNodeSelector.noneEnabled = False
    self.optionalModelNodeSelector.addEnabled = False
    self.optionalModelNodeSelector.removeEnabled = False
    pathFormLayout.addRow("Bronchus model (optional):", self.optionalModelNodeSelector)
    self.parent.connect('mrmlSceneChanged(vtkMRMLScene*)',
                        self.optionalModelNodeSelector, 'setMRMLScene(vtkMRMLScene*)')

    # Input fiducial selector
    self.seedFiducialsNodeSelector = slicer.qSlicerSimpleMarkupsWidget()
    self.seedFiducialsNodeSelector.objectName = 'seedFiducialsNodeSelector'
    self.seedFiducialsNodeSelector.toolTip = "Select a fiducial to use as the origin of the Centerline."
    self.seedFiducialsNodeSelector.setNodeBaseName("OriginSeed")
    self.seedFiducialsNodeSelector.defaultNodeColor = qt.QColor(0,255,0)
    self.seedFiducialsNodeSelector.tableWidget().hide()
    self.seedFiducialsNodeSelector.markupsSelectorComboBox().noneEnabled = False
    self.seedFiducialsNodeSelector.markupsPlaceWidget().placeMultipleMarkups = slicer.qSlicerMarkupsPlaceWidget.ForcePlaceSingleMarkup
    pathFormLayout.addRow("Start point:", self.seedFiducialsNodeSelector)
    self.parent.connect('mrmlSceneChanged(vtkMRMLScene*)',
                        self.seedFiducialsNodeSelector, 'setMRMLScene(vtkMRMLScene*)')

    # CreatePath button
    self.createPathButton = qt.QPushButton("Create path")
    self.createPathButton.toolTip = "Create the path."
    self.createPathButton.enabled = True
    pathFormLayout.addRow(self.createPathButton)
    self.createPathButton.connect('clicked()', self.onCreatePathButtonClicked)

    # Flythrough collapsible button
    flythroughCollapsibleButton = ctk.ctkCollapsibleButton()
    flythroughCollapsibleButton.text = "Flythrough"
    flythroughCollapsibleButton.enabled = True
    self.layout.addWidget(flythroughCollapsibleButton)

    # Layout within the Flythrough collapsible button
    flythroughFormLayout = qt.QFormLayout(flythroughCollapsibleButton)

    # Frame slider
    self.frameSlider = ctk.ctkSliderWidget()
    # self.frameSlider.connect('valueChanged(double)', self.frameSliderValueChanged)
    self.frameSlider.decimals = 0
    flythroughFormLayout.addRow("Frame:", self.frameSlider)

    # Play button
    self.playButton = qt.QPushButton("Play")
    self.playButton.toolTip = "Fly through path."
    self.playButton.checkable = True
    flythroughFormLayout.addRow(self.playButton)
    self.playButton.connect('toggled(bool)', self.onPlayButtonToggled)

    # Add vertical spacer
    self.layout.addStretch(1)

    self.inputModelNodeSelector.setMRMLScene(slicer.mrmlScene)
    self.seedFiducialsNodeSelector.setMRMLScene(slicer.mrmlScene)
    if self.optionalModelNodeSelector.currentNode() is not None:
     self.optionalModelNodeSelector.setMRMLScene(slicer.mrmlScene)


  def findClosestPointOnCenterline(self, point, centerlinePts):
    # given a point in [x, y, z] format and an array of all points on the centerline, return the pt on the centerline that is closest to that point
    min_dist = float("inf")
    current_point = centerlinePts[0]
    closest = current_point

    for i in range(1, len(centerlinePts)):
      current_point = centerlinePts[i]
      dist = np.linalg.norm(np.array(point)-np.array(current_point))
      if dist < min_dist: 
        closest = current_point
        min_dist = dist
    return closest


  def onCreatePathButtonClicked(self):
    """Connected to 'create path' button. It allows to:
      - compute the path
      - create the associated model"""
    from vtk.util import numpy_support as VN

    seedCoordinates = [0,0,0]
    seedNode = self.seedFiducialsNodeSelector.currentNode()
    seedNode.GetNthFiducialPosition(0,seedCoordinates)
    centerline = self.inputModelNodeSelector.currentNode()
    global numPtsOnCenterline
    numPtsOnCenterline = centerline.GetPolyData().GetPointData().GetNumberOfTuples()

    global centerlinePts
    centerlinePts = []
    for i in range(numPtsOnCenterline):
      pt = [0,0,0]
      centerline.GetPolyData().GetPoint((numPtsOnCenterline-i), pt)
      centerlinePts.append(pt)

    # Find point on centerline closest to the seed point
    closestPt = self.findClosestPointOnCenterline(seedCoordinates, centerlinePts)
    closestPtID = centerlinePts.index(closestPt)
    print("closestPt", closestPt)
    print("closestPtID", closestPtID)

    # Determine the scalar array to display and play audio from
    vtkMetricArray = centerline.GetPolyData().GetPointData().GetArray(3)
    activeScalarName = centerline.GetPolyData().GetPointData().GetArrayName(3)
    if vtkMetricArray is None:
      vtkMetricArray = centerline.GetPolyData().GetPointData().GetArray('Radius')
      activeScalarName = 'Radius'

    # Display metric array colortable on centerline
    display = slicer.vtkMRMLModelDisplayNode()
    slicer.mrmlScene.AddNode( display )
    display.SetLineWidth(4)
    self.inputModelNodeSelector.currentNode().SetAndObserveDisplayNodeID( display.GetID() )
    display.SetActiveScalarName(activeScalarName)
    display.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileHotToColdRainbow.txt')
    display.SetScalarVisibility(True)

    # If optional bronchus model was included as input, display the model at low opacity
    if self.optionalModelNodeSelector.currentNode() is not None:
      bronchusDisplay = self.optionalModelNodeSelector.currentNode().GetDisplayNode()
      bronchusDisplay.SetOpacity(0.4)

    global metricArray 
    metricArray = VN.vtk_to_numpy(vtkMetricArray)
    global maxMetric, minMetric
    (maxMetric, minMetric) = self.getMaxAndMinMetrics(metricArray)
    metricArray = np.interp(metricArray, (minMetric, maxMetric), (-12,12))

    # Update frame slider range
    self.frameSlider.maximum = centerline.GetPolyData().GetPointData().GetNumberOfTuples()
    # Change slider position to the pt ID of the selected point on the centerline
    self.frameSlider.value = closestPtID
    self.frameSlider.connect('valueChanged(double)', self.frameSliderValueChanged)

    global sinewave
    sinewave = SineWave(pitch = 0, pitch_per_second = 50)
    sinewave.play()


  def getMaxAndMinMetrics(self, metricArray):
    maxMetric = np.max(metricArray)
    minMetric = np.min(metricArray)
    return (maxMetric, minMetric)


  def playSound(self, metricVal):
    # Play the note, where the pitch is the interpolated metric value
    sinewave.set_pitch(metricVal)
    print("note played: ", metricVal)


  def frameSliderValueChanged(self, newValue):
    print ("frameSliderValueChanged:", newValue)

    newMetricVal = metricArray[numPtsOnCenterline-int(newValue)]
    print("newMetricVal: ", newMetricVal)
    self.playSound(newMetricVal)

    pt = centerlinePts[int(newValue)]
    print("pt: ", pt)
    markupsNode = slicer.util.getNode(slicer.modules.markups.logic().GetActiveListID())
    markupsNode.RemoveAllMarkups()
    slicer.modules.markups.logic().AddFiducial(pt[0], pt[1], pt[2])


  def onPlayButtonToggled(self, checked):
    if checked:
      self.timer.start()
      self.playButton.text = "Stop"
    else:
      self.timer.stop()
      self.playButton.text = "Play"


  def flyToNext(self):
    currentPoint = self.frameSlider.value
    if currentPoint < numPtsOnCenterline:
      self.frameSlider.value = currentPoint + 1
    else:
      self.timer.stop()
      self.playButton.text = "Play"
