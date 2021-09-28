#!/usr/bin/env python

import vtk

import time
from pysinewave import SineWave

def get_program_parameters():
    import argparse
    description = 'Read a polydata file.'
    epilogue = ''''''
    parser = argparse.ArgumentParser(description=description, epilog=epilogue,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('filename', help='Torso.vtp')
    args = parser.parse_args()
    return args.filename


def main():
    colors = vtk.vtkNamedColors()

    filename = get_program_parameters()

    # Read all the data from the file
    reader = vtk.vtkPolyDataReader()
    reader.SetFileName(filename)
    reader.Update()
    
    polyData = reader.GetOutput()
    radiusArray = polyData.GetPointData().GetArray('Radius')
    cell = polyData.GetCell(0)
    cell_ids = cell.GetPointIds()
    
    sinewave = SineWave(pitch = 0, pitch_per_second = 50)
    sinewave.play()
    
    for i in range(cell.GetNumberOfPoints()):
      pt_id = cell_ids.GetId(i)
      pt_r = radiusArray.GetValue(pt_id)
      print(pt_r)
      
      frequency = (pt_r/8 * 48) - 12
      sinewave.set_pitch(frequency)
      time.sleep(0.01)
    
    



if __name__ == '__main__':
    main()
