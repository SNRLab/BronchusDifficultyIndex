import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np
import time

# try:
#   from pysinewave import SineWave
# except: 
#   slicer.util.pip_install('pysinewave')
#   from pysinewave import SineWave

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

    self.endoscopyTimer = qt.QTimer()
    self.endoscopyTimer.setInterval(40)
    self.endoscopyTimer.connect('timeout()', self.endoscopyFlyToNext)


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
    flythroughCollapsibleButton.text = "Audio Flythrough"
    flythroughCollapsibleButton.enabled = True
    self.layout.addWidget(flythroughCollapsibleButton)

    # Layout within the Flythrough collapsible button
    flythroughFormLayout = qt.QFormLayout(flythroughCollapsibleButton)

    # Frame slider
    self.frameSlider = ctk.ctkSliderWidget()
    # self.frameSlider.connect('valueChanged(double)', self.frameSliderValueChanged)
    self.frameSlider.decimals = 0
    flythroughFormLayout.addRow("Frame:", self.frameSlider)

    self.saveFiducialsOnPathCheckbox = qt.QCheckBox()
    self.saveFiducialsOnPathCheckbox.toolTip = "Toggle whether to save the fiducials along the path for use in the endoscopy module (slower)."
    flythroughFormLayout.addRow("Save fiducials for endoscopy : ", self.saveFiducialsOnPathCheckbox)


    # Play button
    self.playButton = qt.QPushButton("Play")
    self.playButton.toolTip = "Fly through path."
    self.playButton.checkable = True
    flythroughFormLayout.addRow(self.playButton)
    self.playButton.connect('toggled(bool)', self.onPlayButtonToggled)


    # ---------- Endoscopy integration --------- #

    # Endoscopy path collapsible button
    endoscopyPathCollapsibleButton = ctk.ctkCollapsibleButton()
    endoscopyPathCollapsibleButton.text = "Endoscopy Path"
    self.layout.addWidget(endoscopyPathCollapsibleButton)

    # Layout within the path collapsible button
    endoscopyPathFormLayout = qt.QFormLayout(endoscopyPathCollapsibleButton)

    # Camera node selector
    self.cameraNodeSelector = slicer.qMRMLNodeComboBox()
    self.cameraNodeSelector.objectName = 'cameraNodeSelector'
    self.cameraNodeSelector.toolTip = "Select a camera that will fly along this path."
    self.cameraNodeSelector.nodeTypes = ['vtkMRMLCameraNode']
    # self.cameraNodeSelector.enabled = True
    self.cameraNodeSelector.noneEnabled = False
    self.cameraNodeSelector.addEnabled = False
    self.cameraNodeSelector.removeEnabled = False
    self.cameraNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setCameraNode)
    endoscopyPathFormLayout.addRow("Camera:", self.cameraNodeSelector)

    # Input fiducials node selector
    self.inputFiducialsNodeSelector = slicer.qMRMLNodeComboBox()
    self.inputFiducialsNodeSelector.objectName = 'inputFiducialsNodeSelector'
    self.inputFiducialsNodeSelector.toolTip = "Select a fiducial list to define control points for the path."
    self.inputFiducialsNodeSelector.nodeTypes = ['vtkMRMLMarkupsFiducialNode', 'vtkMRMLMarkupsCurveNode',
      'vtkMRMLAnnotationHierarchyNode', 'vtkMRMLFiducialListNode']
    self.inputFiducialsNodeSelector.enabled = True
    # self.inputFiducialsNodeSelector.noneEnabled = False
    # self.inputFiducialsNodeSelector.addEnabled = False
    # self.inputFiducialsNodeSelector.removeEnabled = False
    endoscopyPathFormLayout.addRow("Input Fiducials:", self.inputFiducialsNodeSelector)

    # Output path node selector
    self.outputPathNodeSelector = slicer.qMRMLNodeComboBox()
    self.outputPathNodeSelector.objectName = 'outputPathNodeSelector'
    self.outputPathNodeSelector.toolTip = "Select a fiducial list to define control points for the path."
    self.outputPathNodeSelector.nodeTypes = ['vtkMRMLModelNode']
    self.outputPathNodeSelector.enabled = True
    # self.outputPathNodeSelector.noneEnabled = False
    # self.outputPathNodeSelector.addEnabled = True
    # self.outputPathNodeSelector.removeEnabled = True
    # self.outputPathNodeSelector.renameEnabled = True
    endoscopyPathFormLayout.addRow("Output Path:", self.outputPathNodeSelector)

    # CreateEndoscopyPath button
    self.createEndoscopyPathButton = qt.QPushButton("Create virtual endoscopy path")
    self.createEndoscopyPathButton.toolTip = "Create the path."
    self.createEndoscopyPathButton.enabled = True
    endoscopyPathFormLayout.addRow(self.createEndoscopyPathButton)
    self.createEndoscopyPathButton.connect('clicked()', self.onCreateEndoscopyPathButtonClicked)

    # Flythrough collapsible button
    self.endoscopyFlythroughCollapsibleButton = ctk.ctkCollapsibleButton()
    self.endoscopyFlythroughCollapsibleButton.text = "Endoscopy Flythrough With Audio"
    self.endoscopyFlythroughCollapsibleButton.enabled = True
    self.layout.addWidget(self.endoscopyFlythroughCollapsibleButton)

    # Layout within the Flythrough collapsible button
    endoscopyFlythroughFormLayout = qt.QFormLayout(self.endoscopyFlythroughCollapsibleButton)

    # Frame slider
    self.endoscopyFrameSlider = ctk.ctkSliderWidget()
    self.endoscopyFrameSlider.connect('valueChanged(double)', self.endoscopyFrameSliderValueChanged)
    self.endoscopyFrameSlider.decimals = 0
    endoscopyFlythroughFormLayout.addRow("Frame:", self.endoscopyFrameSlider)

    # Frame skip slider
    self.frameSkipSlider = ctk.ctkSliderWidget()
    self.frameSkipSlider.connect('valueChanged(double)', self.frameSkipSliderValueChanged)
    self.frameSkipSlider.decimals = 0
    self.frameSkipSlider.minimum = 0
    self.frameSkipSlider.maximum = 50
    endoscopyFlythroughFormLayout.addRow("Frame skip:", self.frameSkipSlider)

    # Frame delay slider
    self.frameDelaySlider = ctk.ctkSliderWidget()
    self.frameDelaySlider.connect('valueChanged(double)', self.frameDelaySliderValueChanged)
    self.frameDelaySlider.decimals = 0
    self.frameDelaySlider.minimum = 5
    self.frameDelaySlider.maximum = 100
    self.frameDelaySlider.suffix = " ms"
    self.frameDelaySlider.value = 100
    endoscopyFlythroughFormLayout.addRow("Frame delay:", self.frameDelaySlider)

    # View angle slider
    self.viewAngleSlider = ctk.ctkSliderWidget()
    self.viewAngleSlider.connect('valueChanged(double)', self.viewAngleSliderValueChanged)
    self.viewAngleSlider.decimals = 0
    self.viewAngleSlider.minimum = 30
    self.viewAngleSlider.maximum = 180
    endoscopyFlythroughFormLayout.addRow("View Angle:", self.viewAngleSlider)

    # Play button
    self.endoscopyPlayButton = qt.QPushButton("Play")
    self.endoscopyPlayButton.toolTip = "Fly through path."
    self.endoscopyPlayButton.checkable = True
    endoscopyFlythroughFormLayout.addRow(self.endoscopyPlayButton)
    self.endoscopyPlayButton.connect('toggled(bool)', self.onEndoscopyPlayButtonToggled)


    self.cameraNodeSelector.setMRMLScene(slicer.mrmlScene)
    self.inputFiducialsNodeSelector.setMRMLScene(slicer.mrmlScene)
    self.outputPathNodeSelector.setMRMLScene(slicer.mrmlScene)

    # ---------- End Endoscopy integration ---------- #


    # Add vertical spacer
    self.layout.addStretch(1)

    self.inputModelNodeSelector.setMRMLScene(slicer.mrmlScene)
    self.seedFiducialsNodeSelector.setMRMLScene(slicer.mrmlScene)
    if self.optionalModelNodeSelector.currentNode() is not None:
     self.optionalModelNodeSelector.setMRMLScene(slicer.mrmlScene)

    # Initialize the IGTLink components
    self.openIGTNode = slicer.vtkMRMLIGTLConnectorNode()
    slicer.mrmlScene.AddNode(self.openIGTNode)
    self.openIGTNode.SetTypeServer(18950)
    self.openIGTNode.Start()
    print("openIGTNode: ", self.openIGTNode)
    self.IGTActive = True

    self.textNode = slicer.vtkMRMLTextNode()
    self.textNode.SetEncoding(3)
    slicer.mrmlScene.AddNode(self.textNode)

    # Open the secondary Python script (which plays the audio outside of Slicer)
    # exec(open("/home/rebeccalisk/Downloads/CenterlineSliderClient.py").read())



  def findClosestPointOnCenterline(self, point):
    # given a point in [x, y, z] format and an array of all points on the centerline, return the pt on the centerline that is closest to that point
    min_dist = float("inf")
    current_point = self.centerlinePts[0]
    closest = current_point

    for i in range(1, len(self.centerlinePts)):
      current_point = self.centerlinePts[i]
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
    #global numPtsOnCenterline
    self.numPtsOnCenterline = centerline.GetPolyData().GetPointData().GetNumberOfTuples()

    #global centerlinePts
    self.centerlinePts = []
    for i in range(self.numPtsOnCenterline):
      pt = [0,0,0]
      centerline.GetPolyData().GetPoint((self.numPtsOnCenterline-i), pt)
      self.centerlinePts.append(pt)

    # Find point on centerline closest to the seed point
    closestPt = self.findClosestPointOnCenterline(seedCoordinates)
    closestPtID = self.centerlinePts.index(closestPt)
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
    if activeScalarName == 'Radius':
      display.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileHotToColdRainbow.txt')
    else:
      display.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
    display.SetScalarVisibility(True)

    # If optional bronchus model was included as input, display the model at low opacity
    if self.optionalModelNodeSelector.currentNode() is not None:
      bronchusDisplay = self.optionalModelNodeSelector.currentNode().GetDisplayNode()
      bronchusDisplay.SetOpacity(0.4)

    #global metricArray 
    self.metricArray = VN.vtk_to_numpy(vtkMetricArray)

    if activeScalarName == 'Radius':
      self.metricArray = np.array([(11-i) for i in self.metricArray])

    global maxMetric, minMetric
    #(maxMetric, minMetric) = self.getMaxAndMinMetrics(self.metricArray)
    (maxMetric, minMetric) = self.getMaxAndMinMetrics()
    self.metricArray = np.interp(self.metricArray, (minMetric, maxMetric), (-12,12))

    # Update frame slider range
    self.frameSlider.maximum = centerline.GetPolyData().GetPointData().GetNumberOfTuples()
    # Change slider position to the pt ID of the selected point on the centerline
    self.frameSlider.value = closestPtID
    self.frameSlider.connect('valueChanged(double)', self.frameSliderValueChanged)

    # self.sinewave = SineWave(pitch = 0, pitch_per_second = 50)
    # self.sinewave.play()


  # def getMaxAndMinMetrics(self, metricArray):
  def getMaxAndMinMetrics(self):
    maxMetric = np.max(self.metricArray)
    minMetric = np.min(self.metricArray)
    return (maxMetric, minMetric)


  # def playSound(self, metricVal):
  #   # Play the note, where the pitch is the interpolated metric value
  #   self.sinewave.set_pitch(metricVal)
  #   print("note played: ", metricVal)


  def frameSliderValueChanged(self, newValue):
    print ("frameSliderValueChanged:", newValue)

    newMetricVal = self.metricArray[self.numPtsOnCenterline-int(newValue)]
    print("newMetricVal: ", newMetricVal)
    # self.playSound(newMetricVal)
    self.sendTextNode(newMetricVal)

    pt = self.centerlinePts[int(newValue)]
    print("pt: ", pt)
    markupsNode = slicer.util.getNode(slicer.modules.markups.logic().GetActiveListID())
    
    if not self.saveFiducialsOnPathCheckbox.isChecked():
      markupsNode.RemoveAllMarkups()
      slicer.modules.markups.logic().AddFiducial(pt[0], pt[1], pt[2])
    else:
      num_markups = markupsNode.GetNumberOfMarkups() #new
      print("num_markups: ", num_markups)
      if not newValue%50 == 0:
        markupsNode.RemoveMarkup(num_markups-1)
      slicer.modules.markups.logic().AddFiducial(pt[0], pt[1], pt[2])
      

  def onPlayButtonToggled(self, checked):
    if checked:
      self.timer.start()
      self.playButton.text = "Stop"

      self.openIGTNode.RegisterOutgoingMRMLNode(self.textNode)
      self.textNode.SetText("Play")
      self.openIGTNode.PushNode(self.textNode)

    else:
      self.timer.stop()
      self.playButton.text = "Play"

      self.openIGTNode.RegisterOutgoingMRMLNode(self.textNode)
      self.textNode.SetText("Stop")
      self.openIGTNode.PushNode(self.textNode)


  def flyToNext(self):
    currentPoint = self.frameSlider.value
    if currentPoint < (self.numPtsOnCenterline-1):
      self.frameSlider.value = currentPoint + 1
    else:
      self.timer.stop()
      self.playButton.text = "Play"
      # New
      self.openIGTNode.RegisterOutgoingMRMLNode(self.textNode)
      self.textNode.SetText("Stop")
      self.openIGTNode.PushNode(self.textNode)


  def sendTextNode(self, metricVal):
    self.openIGTNode.RegisterOutgoingMRMLNode(self.textNode)
    textOutput = str(metricVal)
    self.textNode.SetText(textOutput)
    self.openIGTNode.PushNode(self.textNode)
    print("sending textNode")
    print(self.textNode)

  # ---------- Endoscopy integration --------- #
  def setCameraNode(self, newCameraNode):
    """Allow to set the current camera node.
    Connected to signal 'currentNodeChanged()' emitted by camera node selector."""

    #  Remove previous observer
    if self.cameraNode and self.cameraNodeObserverTag:
      self.cameraNode.RemoveObserver(self.cameraNodeObserverTag)
    if self.camera and self.cameraObserverTag:
      self.camera.RemoveObserver(self.cameraObserverTag)

    newCamera = None
    if newCameraNode:
      newCamera = newCameraNode.GetCamera()
      # Add CameraNode ModifiedEvent observer
      self.cameraNodeObserverTag = newCameraNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onCameraNodeModified)
      # Add Camera ModifiedEvent observer
      self.cameraObserverTag = newCamera.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onCameraNodeModified)

    self.cameraNode = newCameraNode
    self.camera = newCamera

    # Update UI
    self.updateWidgetFromMRML()

  def updateWidgetFromMRML(self):
    if self.camera:
      self.viewAngleSlider.value = self.camera.GetViewAngle()
    if self.cameraNode:
      pass

  def onCameraModified(self, observer, eventid):
    self.updateWidgetFromMRML()

  def onCameraNodeModified(self, observer, eventid):
    self.updateWidgetFromMRML()

  def onCreateEndoscopyPathButtonClicked(self):
    """Connected to 'create path' button. It allows to:
      - compute the path
      - create the associated model"""

    fiducialsNode = self.inputFiducialsNodeSelector.currentNode()
    outputPathNode = self.outputPathNodeSelector.currentNode()
    print("Calculating Path...")
    result = EndoscopyComputePath(fiducialsNode)
    print("-> Computed path contains %d elements" % len(result.path))

    print("Create Model...")
    model = EndoscopyPathModel(result.path, fiducialsNode, outputPathNode)
    print("-> Model created")

    # Make output model visible and increase line thickness
    # TODO
    slicer.modules.models.logic().SetAllModelsVisibility(1)

    # Update frame slider range
    self.endoscopyFrameSlider.maximum = len(result.path) - 2

    # Update flythrough variables
    self.camera = self.camera
    self.transform = model.transform
    self.pathPlaneNormal = model.planeNormal
    self.path = result.path

    # Enable / Disable flythrough button
    self.endoscopyFlythroughCollapsibleButton.enabled = len(result.path) > 0

  def endoscopyFrameSliderValueChanged(self, newValue):
    #print "frameSliderValueChanged:", newValue
    self.flyTo(newValue)

  def endoscopyFlyToNext(self):
    currentStep = self.endoscopyFrameSlider.value
    nextStep = currentStep + self.skip + 1
    if nextStep > len(self.path) - 2:
      nextStep = 0
    self.endoscopyFrameSlider.value = nextStep

  def flyTo(self, pathPointIndex):
    """ Apply the pathPointIndex-th step in the path to the global camera"""

    if self.path is None:
      return

    pathPointIndex = int(pathPointIndex)
    cameraPosition = self.path[pathPointIndex]

    # # New: Play audio given the camera position
    print("Camera position: ", cameraPosition)
    closestPt = self.findClosestPointOnCenterline(cameraPosition)
    print("Closest pt index: ", closestPt)
    closestPtID = self.centerlinePts.index(closestPt)
    print("Closest pt index: ", closestPtID)
    newMetricVal = self.metricArray[self.numPtsOnCenterline-int(closestPtID)]
    print("newMetricVal: ", newMetricVal)
    # self.playSound(newMetricVal)
    self.sendTextNode(newMetricVal)

    # Add a fiducial at the current camera position point
    # markupsNode = slicer.util.getNode(slicer.modules.markups.logic().GetActiveListID())
    # markupsNode.RemoveAllMarkups()
    # print(markupsNode)
    # slicer.modules.markups.logic().AddFiducial(cameraPosition[0], cameraPosition[1], cameraPosition[2])


    wasModified = self.cameraNode.StartModify()

    self.camera.SetPosition(cameraPosition)
    focalPointPosition = self.path[pathPointIndex+1]
    self.camera.SetFocalPoint(*focalPointPosition)
    self.camera.OrthogonalizeViewUp()

    toParent = vtk.vtkMatrix4x4()
    self.transform.GetMatrixTransformToParent(toParent)
    toParent.SetElement(0 ,3, cameraPosition[0])
    toParent.SetElement(1, 3, cameraPosition[1])
    toParent.SetElement(2, 3, cameraPosition[2])

    # Set up transform orientation component so that
    # Z axis is aligned with view direction and
    # Y vector is aligned with the curve's plane normal.
    # This can be used for example to show a reformatted slice
    # using with SlicerIGT extension's VolumeResliceDriver module.
    import numpy as np
    zVec = (focalPointPosition-cameraPosition)/np.linalg.norm(focalPointPosition-cameraPosition)
    yVec = self.pathPlaneNormal
    xVec = np.cross(yVec, zVec)
    xVec /= np.linalg.norm(xVec)
    yVec = np.cross(zVec, xVec)
    toParent.SetElement(0, 0, xVec[0])
    toParent.SetElement(1, 0, xVec[1])
    toParent.SetElement(2, 0, xVec[2])
    toParent.SetElement(0, 1, yVec[0])
    toParent.SetElement(1, 1, yVec[1])
    toParent.SetElement(2, 1, yVec[2])
    toParent.SetElement(0, 2, zVec[0])
    toParent.SetElement(1, 2, zVec[1])
    toParent.SetElement(2, 2, zVec[2])

    self.transform.SetMatrixTransformToParent(toParent)

    self.cameraNode.EndModify(wasModified)
    self.cameraNode.ResetClippingRange()


  def frameSkipSliderValueChanged(self, newValue):
    #print "frameSkipSliderValueChanged:", newValue
    self.skip = int(newValue)

  def frameDelaySliderValueChanged(self, newValue):
    #print "frameDelaySliderValueChanged:", newValue
    self.endoscopyTimer.interval = newValue

  def viewAngleSliderValueChanged(self, newValue):
    if not self.cameraNode:
      return
    #print "viewAngleSliderValueChanged:", newValue
    self.cameraNode.GetCamera().SetViewAngle(newValue)

  def onEndoscopyPlayButtonToggled(self, checked):
    if checked:
      self.endoscopyTimer.start()
      self.endoscopyPlayButton.text = "Stop"
      self.textNode.SetText("Play")

      self.openIGTNode.RegisterOutgoingMRMLNode(self.textNode)
      self.textNode.SetText("Play")
      self.openIGTNode.PushNode(self.textNode)

    else:
      self.endoscopyTimer.stop()
      self.endoscopyPlayButton.text = "Play"

      self.openIGTNode.RegisterOutgoingMRMLNode(self.textNode)
      self.textNode.SetText("Stop")
      self.openIGTNode.PushNode(self.textNode)


class EndoscopyComputePath:
  """Compute path given a list of fiducials.
  Path is stored in 'path' member variable as a numpy array.
  If a point list is received then curve points are generated using Hermite spline interpolation.
  See http://en.wikipedia.org/wiki/Cubic_Hermite_spline
  Example:
    result = EndoscopyComputePath(fiducialListNode)
    print "computer path has %d elements" % len(result.path)
  """

  def __init__(self, fiducialListNode, dl = 0.5):
    import numpy
    self.dl = dl # desired world space step size (in mm)
    self.dt = dl # current guess of parametric stepsize
    self.fids = fiducialListNode

    # Already a curve, just get the points, sampled at equal distances.
    if (self.fids.GetClassName() == "vtkMRMLMarkupsCurveNode"
      or self.fids.GetClassName() == "vtkMRMLMarkupsClosedCurveNode"):
      # Temporarily increase the number of points per segment, to get a very smooth curve
      pointsPerSegment = int(self.fids.GetCurveLengthWorld() / self.dl / self.fids.GetNumberOfControlPoints()) + 1
      originalPointsPerSegment = self.fids.GetNumberOfPointsPerInterpolatingSegment()
      if originalPointsPerSegment<pointsPerSegment:
        self.fids.SetNumberOfPointsPerInterpolatingSegment(pointsPerSegment)
      # Get equidistant points
      resampledPoints = vtk.vtkPoints()
      slicer.vtkMRMLMarkupsCurveNode.ResamplePoints(self.fids.GetCurvePointsWorld(), resampledPoints, self.dl, self.fids.GetCurveClosed())
      # Restore original number of pointsPerSegment
      if originalPointsPerSegment<pointsPerSegment:
        self.fids.SetNumberOfPointsPerInterpolatingSegment(originalPointsPerSegment)
      # Get it as a numpy array as an independent copy
      import vtk.util.numpy_support as VN
      self.path = VN.vtk_to_numpy(resampledPoints.GetData())
      return

    # hermite interpolation functions
    self.h00 = lambda t: 2*t**3 - 3*t**2     + 1
    self.h10 = lambda t:   t**3 - 2*t**2 + t
    self.h01 = lambda t:-2*t**3 + 3*t**2
    self.h11 = lambda t:   t**3 -   t**2

    # n is the number of control points in the piecewise curve

    if self.fids.GetClassName() == "vtkMRMLAnnotationHierarchyNode":
      # slicer4 style hierarchy nodes
      collection = vtk.vtkCollection()
      self.fids.GetChildrenDisplayableNodes(collection)
      self.n = collection.GetNumberOfItems()
      if self.n == 0:
        return
      self.p = numpy.zeros((self.n,3))
      for i in range(self.n):
        f = collection.GetItemAsObject(i)
        coords = [0,0,0]
        f.GetFiducialCoordinates(coords)
        self.p[i] = coords
    elif self.fids.GetClassName() == "vtkMRMLMarkupsFiducialNode":
      # slicer4 Markups node
      self.n = self.fids.GetNumberOfControlPoints()
      n = self.n
      if n == 0:
        return
      # get fiducial positions
      # sets self.p
      self.p = numpy.zeros((n,3))
      for i in range(n):
        coord = [0.0, 0.0, 0.0]
        self.fids.GetNthControlPointPositionWorld(i, coord)
        self.p[i] = coord
    else:
      # slicer3 style fiducial lists
      self.n = self.fids.GetNumberOfFiducials()
      n = self.n
      if n == 0:
        return
      # get control point data
      # sets self.p
      self.p = numpy.zeros((n,3))
      for i in range(n):
        self.p[i] = self.fids.GetNthFiducialXYZ(i)

    # calculate the tangent vectors
    # - fm is forward difference
    # - m is average of in and out vectors
    # - first tangent is out vector, last is in vector
    # - sets self.m
    n = self.n
    fm = numpy.zeros((n,3))
    for i in range(0,n-1):
      fm[i] = self.p[i+1] - self.p[i]
    self.m = numpy.zeros((n,3))
    for i in range(1,n-1):
      self.m[i] = (fm[i-1] + fm[i]) / 2.
    self.m[0] = fm[0]
    self.m[n-1] = fm[n-2]

    self.path = [self.p[0]]
    self.calculatePath()

  def calculatePath(self):
    """ Generate a flight path for of steps of length dl """
    #
    # calculate the actual path
    # - take steps of self.dl in world space
    # -- if dl steps into next segment, take a step of size "remainder" in the new segment
    # - put resulting points into self.path
    #
    n = self.n
    segment = 0 # which first point of current segment
    t = 0 # parametric current parametric increment
    remainder = 0 # how much of dl isn't included in current step
    while segment < n-1:
      t, p, remainder = self.step(segment, t, self.dl)
      if remainder != 0 or t == 1.:
        segment += 1
        t = 0
        if segment < n-1:
          t, p, remainder = self.step(segment, t, remainder)
      self.path.append(p)

  def point(self,segment,t):
    return (self.h00(t)*self.p[segment] +
              self.h10(t)*self.m[segment] +
              self.h01(t)*self.p[segment+1] +
              self.h11(t)*self.m[segment+1])

  def step(self,segment,t,dl):
    """ Take a step of dl and return the path point and new t
      return:
      t = new parametric coordinate after step
      p = point after step
      remainder = if step results in parametric coordinate > 1.0, then
        this is the amount of world space not covered by step
    """
    import numpy.linalg
    p0 = self.path[self.path.__len__() - 1] # last element in path
    remainder = 0
    ratio = 100
    count = 0
    while abs(1. - ratio) > 0.05:
      t1 = t + self.dt
      pguess = self.point(segment,t1)
      dist = numpy.linalg.norm(pguess - p0)
      ratio = self.dl / dist
      self.dt *= ratio
      if self.dt < 0.00000001:
        return
      count += 1
      if count > 500:
        return (t1, pguess, 0)
    if t1 > 1.:
      t1 = 1.
      p1 = self.point(segment, t1)
      remainder = numpy.linalg.norm(p1 - pguess)
      pguess = p1
    return (t1, pguess, remainder)


class EndoscopyPathModel:
  """Create a vtkPolyData for a polyline:
       - Add one point per path point.
       - Add a single polyline
  """
  def __init__(self, path, fiducialListNode, outputPathNode=None, cursorType=None):
    """
      :param path: path points as numpy array.
      :param fiducialListNode: input node, just used for naming the output node.
      :param outputPathNode: output model node that stores the path points.
      :param cursorType: can be 'markups' or 'model'. Markups has a number of advantages (radius it is easier to change the size,
        can jump to views by clicking on it, has more visualization options, can be scaled to fixed display size),
        but if some applications relied on having a model node as cursor then this argument can be used to achieve that.
    """

    fids = fiducialListNode
    scene = slicer.mrmlScene

    self.cursorType = "markups" if cursorType is None else cursorType

    points = vtk.vtkPoints()
    polyData = vtk.vtkPolyData()
    polyData.SetPoints(points)

    lines = vtk.vtkCellArray()
    polyData.SetLines(lines)
    linesIDArray = lines.GetData()
    linesIDArray.Reset()
    linesIDArray.InsertNextTuple1(0)

    polygons = vtk.vtkCellArray()
    polyData.SetPolys( polygons )
    idArray = polygons.GetData()
    idArray.Reset()
    idArray.InsertNextTuple1(0)

    for point in path:
      pointIndex = points.InsertNextPoint(*point)
      linesIDArray.InsertNextTuple1(pointIndex)
      linesIDArray.SetTuple1( 0, linesIDArray.GetNumberOfTuples() - 1 )
      lines.SetNumberOfCells(1)

    import vtk.util.numpy_support as VN
    pointsArray = VN.vtk_to_numpy(points.GetData())
    self.planePosition, self.planeNormal = self.planeFit(pointsArray.T)

    # Create model node
    model = outputPathNode
    if not model:
      model = scene.AddNewNodeByClass("vtkMRMLModelNode", scene.GenerateUniqueName("Path-%s" % fids.GetName()))
      model.CreateDefaultDisplayNodes()
      model.GetDisplayNode().SetColor(1,1,0) # yellow

    model.SetAndObservePolyData(polyData)

    # Camera cursor
    cursor = model.GetNodeReference("CameraCursor")
    if not cursor:

      if self.cursorType == "markups":
        # Markups cursor
        cursor = scene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", scene.GenerateUniqueName("Cursor-%s" % fids.GetName()))
        cursor.CreateDefaultDisplayNodes()
        cursor.GetDisplayNode().SetSelectedColor(1,0,0)  # red
        cursor.GetDisplayNode().SetSliceProjection(True)
        cursor.AddControlPoint(vtk.vtkVector3d(0,0,0)," ")  # do not show any visible label
        cursor.SetNthControlPointLocked(0, True)
      else:
        # Model cursor
        cursor = scene.AddNewNodeByClass("vtkMRMLMarkupsModelNode", scene.GenerateUniqueName("Cursor-%s" % fids.GetName()))
        cursor.CreateDefaultDisplayNodes()
        cursor.GetDisplayNode().SetColor(1,0,0)  # red
        cursor.GetDisplayNode().BackfaceCullingOn()  # so that the camera can see through the cursor from inside
        # Add a sphere as cursor
        sphere = vtk.vtkSphereSource()
        sphere.Update()
        cursor.SetPolyDataConnection(sphere.GetOutputPort())

      model.SetNodeReferenceID("CameraCursor", cursor.GetID())

    # Transform node
    transform = model.GetNodeReference("CameraTransform")
    if not transform:
      transform = scene.AddNewNodeByClass("vtkMRMLLinearTransformNode", scene.GenerateUniqueName("Transform-%s" % fids.GetName()))
      model.SetNodeReferenceID("CameraTransform", transform.GetID())
    cursor.SetAndObserveTransformNodeID(transform.GetID())

    self.transform = transform

  # source: http://stackoverflow.com/questions/12299540/plane-fitting-to-4-or-more-xyz-points
  def planeFit(self, points):
    """
    p, n = planeFit(points)
    Given an array, points, of shape (d,...)
    representing points in d-dimensional space,
    fit an d-dimensional plane to the points.
    Return a point, p, on the plane (the point-cloud centroid),
    and the normal, n.
    """
    import numpy as np
    from numpy.linalg import svd
    points = np.reshape(points, (np.shape(points)[0], -1)) # Collapse trialing dimensions
    assert points.shape[0] <= points.shape[1], f"There are only {points.shape[1]} points in {points.shape[0]} dimensions."
    ctr = points.mean(axis=1)
    x = points - ctr[:,np.newaxis]
    M = np.dot(x, x.T) # Could also use np.cov(x) here.
    return ctr, svd(M)[0][:,-1]
