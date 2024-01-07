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

    bg_list = []
    gr_list = []
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

            bg = b / g
            gr = g / r

            bg_list.append(bg)
            gr_list.append(gr)

            red_detection = "other"
            if (h > 0.93) and (s > 0.60 and s < 0.81):
                red_detection = "RED"
            elif (h > 0.93 and h < 0.98) and (s > 0.53 and s < 0.60):
                red_detection = "YELLOW"
            elif (h > 0.55 and h < 0.62) and (s > 0.50 and s < 0.72):
                red_detection = "LIGHT BLUE"
            elif (h > 0.15 and h < 0.30) and (s > 0.23 and s < 0.55):
                red_detection = "LIGHT GREEN"
            elif (h > 0.40 and h < 0.60) and (s > 0.25 and s < 0.60):
                red_detection = "GREEN"
            elif (h > 0.58 and h < 0.78) and (s > 0.19 and s < 0.40):
                red_detection = "DARK GRAY (track)"


            # print(demo_color_sensor.cnt, limit, args, kwargs, h, s, v, bg, gr, red_detection)
            print(r, ",", g, ",", b)

    smart_hub.vision_sensor.subscribe(callback, granularity=2, mode=6)

    while demo_color_sensor.cnt < LIMIT:
        sleep(1)

    smart_hub.vision_sensor.unsubscribe(callback)

    print("H stats: ", stat.mean(h_list), stat.stdev(h_list), min(h_list), max(h_list))
    print("S stats: ", stat.mean(s_list), stat.stdev(s_list), min(s_list), max(s_list))
    print("V stats: ", stat.mean(v_list), stat.stdev(v_list), min(v_list), max(v_list))
    print("BG stats: ", stat.mean(bg_list), stat.stdev(bg_list), min(bg_list), max(bg_list))
    print("GR stats: ", stat.mean(gr_list), stat.stdev(gr_list), min(gr_list), max(gr_list))

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

if __name__ == '__main__':
    smart_hub = SmartHub(address=uuid_definitions.HUB_ORIG)   # original hub
    demo_color_sensor(smart_hub)

    # # alternate form that reads RGB data from file
    # rgb_list = ingest("data/Final_green_2.csv")
    #
    # h_list = []
    # s_list = []
    # v_list = []
    #
    # for rgb in rgb_list:
    #     h, s, v = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
    #     h_list.append(h)
    #     s_list.append(s)
    #     v_list.append(v)
    #
    # print("H stats: ", stat.mean(h_list), stat.stdev(h_list), min(h_list), max(h_list))
    # print("S stats: ", stat.mean(s_list), stat.stdev(s_list), min(s_list), max(s_list))
    # print("V stats: ", stat.mean(v_list), stat.stdev(v_list), min(v_list), max(v_list))

#--------------- RESULTS -----------------

# Gray (Gray_track_RGB.csv):
# H stats:  0.684 0.0377      0.611  0.767
# S stats:  0.291 0.0478      0.190  0.429
# V stats:  21.394 0.6206    21.0   24.0

# Azur (Azur_tile_RGB.csv):
# H stats:  0.597 0.0048      0.583  0.609
# S stats:  0.632 0.0277      0.575  0.714
# V stats:  55.168 0.757     52.0   57.0

# Red (Red_tile_RGB.csv):
# H stats:  0.965 0.0062     0.952  0.982
# S stats:  0.714 0.0231     0.643  0.756
# V stats:  42.427 1.444    39.0 46.0

# Green 1
# H stats:  0.465 0.0174     0.4167 0.538
# S stats:  0.455 0.038      0.3333 0.55
# V stats:  19.5367 0.7237  17.0 21.0

# Green 1
# H stats:  0.464   0.0184     0.4167 0.5278
# S stats:  0.4457  0.0400     0.3    0.55
# V stats:  19.412  0.9035    17.0   21.0
