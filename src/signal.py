'''
This file contains colorimetry data used to sense the signal tiles.
'''

RED = "RED"
GREEN = "GREEN"
BLUE = "BLUE"
YELLOW = "YELLOW"
PURPLE = "PURPLE"   # may slightly overlap with RED

# this is used to refer to the colorless inter-sector zone
INTER_SECTOR = "inter-sector"

# Vision sensor colorimetry parameters.
RGB_MINIMUM = 10.0
V_MINIMUM = 100.

HUE = {}
SATURATION = {}

HUE[RED]    = (0.985, 1.01)  # min and max hue
HUE[GREEN]  = (0.35,  0.40)
HUE[BLUE]   = (0.55,  0.60)
HUE[YELLOW] = (0.09,  0.13)
HUE[PURPLE] = (0.95,  0.97)

SATURATION[RED]    = (0.78, 0.88)  # min and max saturation
SATURATION[GREEN]  = (0.66, 0.81)
SATURATION[BLUE]   = (0.76, 0.86)
SATURATION[YELLOW] = (0.55, 0.63)
SATURATION[PURPLE] = (0.72, 0.83)
