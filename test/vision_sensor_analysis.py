import glob

import statistics as stat
import csv
from time import sleep
from colorsys import rgb_to_hsv
import numpy as np

from pylgbst.hub import SmartHub
from src import uuid_definitions

LIMIT = 600


def demo_color_sensor(smart_hub):
    print("Color sensor test: wave your hand in front of it")
    demo_color_sensor.cnt = 0

    h_list = []
    s_list = []
    v_list = []

    def callback(*args, **kwargs):
        demo_color_sensor.cnt += 1

        # use HSV as criterion for mapping colors
        r = args[0]
        g = args[1]
        b = args[2]

        h, s, v = rgb_to_hsv(r, g, b)

        if h >= 1. or h <= 0.:
            return

        if max(r, g, b) > 0.0 and v > 0.0:
            h_list.append(h)
            s_list.append(s)
            v_list.append(v)

            print(r, ",", g, ",", b)

    smart_hub.vision_sensor.subscribe(callback, granularity=2, mode=6)

    while demo_color_sensor.cnt < LIMIT:
        sleep(1)

    smart_hub.vision_sensor.unsubscribe(callback)

    print("H stats: ", stat.mean(h_list), stat.stdev(h_list), min(h_list), max(h_list))
    print("S stats: ", stat.mean(s_list), stat.stdev(s_list), min(s_list), max(s_list))
    print("V stats: ", stat.mean(v_list), stat.stdev(v_list), min(v_list), max(v_list))

def demo_color_sensor_modes(smart_hub, mode):
    def callback(*args, **kwargs):
        print(args, kwargs)

    smart_hub.vision_sensor.subscribe(callback, granularity=0, mode=mode)

    while 1:
        pass

def ingest(filename):
    points_list = []
    with open(filename, mode='r') as csv_file:
        csv_reader = csv.reader(csv_file)
        for row in csv_reader:
            points_list.append(np.array(row, dtype=float))

    RGB_list = []
    for point in points_list:
        RGB_list.append(point / 1)

    return RGB_list

def from_files():
    filelist = glob.glob("data/*")
    filelist.remove("data/lego_colors.csv")

    for filename in filelist:

        rgb_table = ingest(filename)

        h_list = []
        s_list = []
        v_list = []
        r_list = []
        g_list = []
        b_list = []

        for rgb in rgb_table:
            h, s, v = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
            h_list.append(h)
            s_list.append(s)
            v_list.append(v)
            r_list.append(rgb[0])
            g_list.append(rgb[1])
            b_list.append(rgb[2])

        print(filename)
        print("H stats: ", stat.mean(h_list), stat.stdev(h_list), min(h_list), max(h_list))
        print("S stats: ", stat.mean(s_list), stat.stdev(s_list), min(s_list), max(s_list))
        print("V stats: ", stat.mean(v_list), stat.stdev(v_list), min(v_list), max(v_list))
        print("R stats: ", stat.mean(r_list), stat.stdev(r_list), min(r_list), max(r_list))
        print("G stats: ", stat.mean(g_list), stat.stdev(g_list), min(g_list), max(g_list))
        print("B stats: ", stat.mean(b_list), stat.stdev(b_list), min(b_list), max(b_list))
        print()

if __name__ == '__main__':
    # smart_hub = SmartHub(address=uuid_definitions.HUB_ORIG)   # original hub
    # demo_color_sensor(smart_hub)
    # demo_color_sensor_modes(smart_hub, 6)

    # alternate form that reads RGB data from previously collected files
    from_files()


