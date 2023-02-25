import json
import logging
import time

from pylgbst.hub import SmartHub, RemoteHandset
from pylgbst.peripherals import Peripheral, EncodedMotor, TiltSensor, Current, Voltage, COLORS, COLOR_BLACK, COLOR_GREEN

logging.basicConfig(level=logging.DEBUG)

# hub = SmartHub(address='86996732-BF5A-433D-AACE-5611D4C6271D')   # test hub
# hub = HandsetRemote(address='2BC6E69B-5F56-4716-AD8C-7B4D5CBC7BF8')  # test handset
hub = RemoteHandset(address='5D319849-7D59-4EBB-A561-0C37C5EF8DCD')  # train handset

descr = {}
values = hub.peripherals.values()

print("@@@@ test5.py 15: ", values)

for dev in values:
    # descr[str(dev)] = dev.describe_possible_modes()
    # print("@@@@ test5.py 15: ", dev)
    print("@@@@ test5.py 16: ", dev.describe_possible_modes())

# print(descr)
#
# with open("descr.json", "w") as fhd:
#     json.dump(descr, fhd, indent=True)
