#!/usr/bin/env python

import vtk

import time
from pysinewave import SineWave
import pyigtl

def main():
		
	client = pyigtl.OpenIGTLinkClient("127.0.0.1", 18950)
	sinewave = SineWave(pitch = 0, pitch_per_second = 50)
	#sinewave.play()

	while client is not None:
		message = client.wait_for_message("Text", timeout=50)
		print(message.string)
	
		if message.string == "Play":
			sinewave.play()
		elif message.string == "Stop":
			sinewave.stop()
		else:
			sinewave.set_pitch(float(message.string))
			#time.sleep(0.1)

if __name__ == '__main__':
    main()

